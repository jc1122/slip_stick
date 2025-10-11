#!/usr/bin/env python3
"""Run the slipstick CLI across all CSVs in the datasets/ directory.

Saves analysis plots to plots/analysis, noise plots to plots/noise, spectra to plots/spectra
and writes textual summaries to summaries/<dataset>.txt. Also creates a per-dataset
spectra summary image under plots/spectra.
"""
from pathlib import Path
from subprocess import run, CalledProcessError
from time import perf_counter, sleep
import json
import math
import os
import argparse
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor, as_completed
import psutil


def _worker(args_tuple):
    # Runs in worker process
    fpath, plot_dir_s, noise_dir_s, spec_dir_s, spec_summary_s, summaries_dir_s, plot_workers = args_tuple
    f = Path(fpath)
    stem = f.stem
    out_summary = Path(summaries_dir_s) / f"{stem}.txt"
    spec_summary = Path(spec_summary_s)

    cmd = [
        "python3",
        "-m",
        "slipstick.cli",
        "--input",
        str(f),
        "--plot-dir",
        plot_dir_s,
        "--noise-plot-dir",
        noise_dir_s,
        "--spectra-plot-dir",
        spec_dir_s,
        "--spectra-summary",
        str(spec_summary),
        "--plot-format",
        "png",
        "--plot-workers",
        str(plot_workers),
    ]

    env = os.environ.copy()
    env.update({"MPLBACKEND": "module://mplcairo.base"})

    t0 = perf_counter()
    try:
        res = run(cmd, check=False, capture_output=True, text=True, env=env)
        t1 = perf_counter()
        # write stdout to summary file
        out_summary.write_text(res.stdout or "")
        if res.stderr:
            # also write stderr to .err file
            err_path = Path(summaries_dir_s) / f"{stem}.err"
            err_path.write_text(res.stderr)

        success = res.returncode == 0
        returncode = res.returncode
    except Exception as exc:
        t1 = perf_counter()
        success = False
        returncode = -1
        out_summary.write_text(f"Exception running CLI: {exc}\n")

    duration = t1 - t0

    # count plots
    analysis_count = len(list(Path(plot_dir_s).glob(f"{stem}_*.*")))
    noise_count = len(list(Path(noise_dir_s).glob(f"{stem}_*_noise.*")))
    spectrum_count = len(list(Path(spec_dir_s).glob(f"{stem}_*_spectrum.*")))
    spectra_summary_exists = spec_summary.exists()

    # Remove lock file on completion
    try:
        lock_file = Path(summaries_dir_s) / f"{stem}.lock"
        if lock_file.exists():
            lock_file.unlink()
    except Exception:
        pass

    return {
        "dataset": f.name,
        "stem": stem,
        "success": success,
        "returncode": returncode,
        "duration_s": round(duration, 4),
        "analysis_plots": analysis_count,
        "noise_plots": noise_count,
        "spectrum_plots": spectrum_count,
        "spectra_summary": bool(spectra_summary_exists),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run slipstick analysis across all CSV datasets")
    parser.add_argument("--slipstick-workers", type=int, default=1, 
                       help="Number of concurrent slipstick jobs (default: 1)")
    parser.add_argument("--plot-workers", type=int, default=1,
                       help="Number of plot workers per slipstick job (default: 1)")
    parser.add_argument("--max-datasets", type=int, default=None,
                       help="Limit number of datasets to process (default: all)")
    args = parser.parse_args()
    
    print(f"Starting run_all.py with {args.slipstick_workers} slipstick workers, {args.plot_workers} plot workers per job")
    
    workspace = Path(__file__).resolve().parents[1]
    dataset_dir = workspace / "datasets"
    plot_dir = workspace / "plots" / "analysis"
    noise_dir = workspace / "plots" / "noise"
    spec_dir = workspace / "plots" / "spectra"
    summaries_dir = workspace / "summaries"

    for d in (plot_dir, noise_dir, spec_dir, summaries_dir):
        d.mkdir(parents=True, exist_ok=True)

    csvs = sorted(dataset_dir.glob("*.csv"))
    print(f"Found {len(csvs)} CSV files in {dataset_dir}")
    if not csvs:
        print("No CSV files found in datasets/")
        return 1

    # Build job list with atomic lock creation to avoid duplicates
    jobs = []
    for f in csvs:
        stem = f.stem
        out_summary = summaries_dir / f"{stem}.txt"
        spec_summary = spec_dir / f"{stem}_spectra_summary.png"

        if out_summary.exists():
            print(f"Skipping {f.name} (summary exists)")
            continue

        lock_path = summaries_dir / f"{stem}.lock"
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            print(f"Skipping {f.name} (lock exists)")
            continue

        jobs.append((str(f), str(plot_dir), str(noise_dir), str(spec_dir), str(spec_summary), str(summaries_dir), args.plot_workers))

    total = len(jobs)
    if total == 0:
        print("No new jobs to process. Exiting.")
        return 0

    # Limit datasets if specified
    if args.max_datasets:
        jobs = jobs[:args.max_datasets]
        total = len(jobs)
        print(f"Limited to {total} datasets")

    metrics = []
    start_all = perf_counter()
    print(f"Process started at {start_all:.1f}s")
    
    # Use specified number of slipstick workers
    max_workers = min(args.slipstick_workers, cpu_count())
    print(f"Submitting {total} jobs with up to {max_workers} slipstick workers (each using {args.plot_workers} plot workers)")

    # Start CPU monitoring in background
    cpu_samples = []
    monitoring = True
    
    def monitor_cpu():
        while monitoring:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_samples.append(cpu_percent)
    
    import threading
    monitor_thread = threading.Thread(target=monitor_cpu, daemon=True)
    monitor_thread.start()

    # Submit jobs to executor
    futures = {}
    submit_start = perf_counter()
    print(f"All jobs submitted at {submit_start - start_all:.1f}s elapsed")
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        # submit jobs and create an in-progress marker so users see activity
        for job in jobs:
            fpath = job[0]
            stem = Path(fpath).stem
            inprog = Path(summaries_dir) / f"{stem}.inprogress"
            try:
                inprog.write_text("started")
            except Exception:
                pass
            print(f"Submitting job for {stem}")
            fut = ex.submit(_worker, job)
            futures[fut] = job[0]

        completed = 0
        for fut in as_completed(futures):
            try:
                result = fut.result()
            except Exception as exc:
                # If the worker crashed, attempt to recover lock removal and record failure
                dataset_path = futures.get(fut, "unknown")
                stem = Path(dataset_path).stem if dataset_path != "unknown" else "unknown"
                lock_file = summaries_dir / f"{stem}.lock"
                if lock_file.exists():
                    try:
                        lock_file.unlink()
                    except Exception:
                        pass
                print(f"Job failed for {dataset_path}: {exc}")
                result = {
                    "dataset": dataset_path,
                    "stem": stem,
                    "success": False,
                    "returncode": -1,
                    "duration_s": 0.0,
                    "analysis_plots": 0,
                    "noise_plots": 0,
                    "spectrum_plots": 0,
                    "spectra_summary": False,
                }

            metrics.append(result)
            completed += 1
            # remove inprogress marker if present
            try:
                inprog = Path(summaries_dir) / f"{Path(result['dataset']).stem}.inprogress"
                if inprog.exists():
                    inprog.unlink()
            except Exception:
                pass
            avg = sum(m["duration_s"] for m in metrics) / len(metrics)
            remaining = total - completed
            eta = avg * remaining
            print(
                f"[{completed}/{total}] Completed {result['dataset']} — {result['duration_s']:.2f}s; plots: analysis={result['analysis_plots']}, noise={result['noise_plots']}, spectra={result['spectrum_plots']}; ETA {eta:.1f}s ({math.ceil(eta/60)}m)"
            )

    # Stop CPU monitoring
    monitoring = False
    monitor_thread.join(timeout=2)

    total_time = perf_counter() - start_all
    completion_time = perf_counter()
    print(f"All jobs completed at {completion_time - start_all:.1f}s elapsed (processing took {total_time:.1f}s)")
    
    bench_out = summaries_dir / "benchmarks.json"
    
    # Calculate CPU usage statistics
    if cpu_samples:
        avg_cpu = sum(cpu_samples) / len(cpu_samples)
        max_cpu = max(cpu_samples)
        min_cpu = min(cpu_samples)
        cpu_stats = {
            "avg_cpu_percent": round(avg_cpu, 1),
            "max_cpu_percent": round(max_cpu, 1),
            "min_cpu_percent": round(min_cpu, 1),
            "cpu_samples_count": len(cpu_samples)
        }
        print(f"\nCPU Usage: Avg {avg_cpu:.1f}%, Max {max_cpu:.1f}%, Min {min_cpu:.1f}%")
    else:
        cpu_stats = {"error": "No CPU samples collected"}
    
    with bench_out.open("w") as fh:
        json.dump({
            "cpu_count": cpu_count(), 
            "total_time_s": round(total_time, 3),
            "submit_time_s": round(submit_start - start_all, 3),
            "processing_time_s": round(completion_time - submit_start, 3),
            "cpu_stats": cpu_stats,
            "config": {
                "slipstick_workers": args.slipstick_workers,
                "plot_workers": args.plot_workers,
                "max_datasets": args.max_datasets
            },
            "files": metrics
        }, fh, indent=2)

    if metrics:
        durations = [m["duration_s"] for m in metrics]
        print("\nBenchmark summary:")
        print(f"  Configuration: {args.slipstick_workers} slipstick workers, {args.plot_workers} plot workers each")
        print(f"  Datasets processed: {len(metrics)}/{total}")
        print(f"  Setup time: {(submit_start - start_all):.1f}s")
        print(f"  Processing time: {(completion_time - submit_start):.1f}s")
        print(f"  Total wall time: {total_time:.1f}s ({total_time/60:.1f}m)")
        print(f"  Avg per dataset: {sum(durations)/len(durations):.1f}s")
        print(f"  Fastest: {min(durations):.1f}s, Slowest: {max(durations):.1f}s")
        print(f"  Benchmarks written to: {bench_out}")

    print("All files processed.")
    return 0
