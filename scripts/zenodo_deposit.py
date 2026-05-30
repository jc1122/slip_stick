#!/usr/bin/env python3
"""Reserve and manage the Zenodo draft record for this archive.

This helper intentionally avoids third-party dependencies. It uses the Zenodo
REST API directly and reads the access token from ZENODO_ACCESS_TOKEN.
It never publishes a record unless --publish is passed explicitly.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_API = "https://zenodo.org/api"


class ZenodoError(RuntimeError):
    """Raised for API or local state failures."""


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def _token() -> str:
    token = os.environ.get("ZENODO_ACCESS_TOKEN")
    if not token:
        raise ZenodoError(
            "ZENODO_ACCESS_TOKEN is not set. Create a Zenodo personal access "
            "token with deposit/write scope and export it before running."
        )
    return token


def _request(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict | None = None,
    data: bytes | None = None,
    content_type: str | None = "application/json",
) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    body: bytes | None = data
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if body is not None and content_type:
        headers["Content-Type"] = content_type

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ZenodoError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ZenodoError(f"{method} {url} failed: {exc}") from exc

    if not response_body:
        return {}
    return json.loads(response_body.decode("utf-8"))


def _metadata_payload(metadata_path: Path) -> dict:
    metadata = _load_json(metadata_path)
    metadata["prereserve_doi"] = True
    return {"metadata": metadata}


def reserve(args: argparse.Namespace) -> int:
    payload = _metadata_payload(args.metadata)
    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    result = _request(
        "POST",
        f"{args.api_url.rstrip('/')}/deposit/depositions",
        token=_token(),
        payload=payload,
    )
    _write_json(args.output, result)

    doi = result.get("metadata", {}).get("prereserve_doi", {}).get("doi")
    deposition_id = result.get("id")
    if not doi or not deposition_id:
        raise ZenodoError(f"Zenodo response did not contain reserved DOI/id: {args.output}")

    args.doi_output.write_text(f"{doi}\n", encoding="utf-8")
    print(f"Reserved DOI: {doi}")
    print(f"Draft deposition id: {deposition_id}")
    print(f"Wrote: {args.output}")
    print(f"Wrote: {args.doi_output}")
    return 0


def upload(args: argparse.Namespace) -> int:
    deposition = _load_json(args.deposition_json)
    bucket = deposition.get("links", {}).get("bucket")
    if not bucket:
        raise ZenodoError(f"No bucket link found in {args.deposition_json}")

    file_path = args.file
    url = f"{bucket.rstrip('/')}/{urllib.parse.quote(file_path.name)}"
    result = _request(
        "PUT",
        url,
        token=_token(),
        data=file_path.read_bytes(),
        content_type="application/octet-stream",
    )
    print(f"Uploaded: {file_path.name}")
    print(f"File id: {result.get('id', '<unknown>')}")
    print(f"Size: {result.get('filesize', file_path.stat().st_size)} bytes")
    return 0


def publish(args: argparse.Namespace) -> int:
    deposition = _load_json(args.deposition_json)
    deposition_id = deposition.get("id")
    if not deposition_id:
        raise ZenodoError(f"No deposition id found in {args.deposition_json}")
    if not args.publish:
        raise ZenodoError("Refusing to publish without --publish.")

    result = _request(
        "POST",
        f"{args.api_url.rstrip('/')}/deposit/depositions/{deposition_id}/actions/publish",
        token=_token(),
    )
    conceptdoi = result.get("conceptdoi", "<unknown>")
    doi = result.get("doi", "<unknown>")
    print(f"Published deposition {deposition_id}")
    print(f"DOI: {doi}")
    print(f"Concept DOI: {conceptdoi}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API, help="Zenodo API base URL.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    reserve_parser = subparsers.add_parser("reserve", help="Create a draft record and reserve a DOI.")
    reserve_parser.add_argument("--metadata", type=Path, default=Path(".zenodo.json"))
    reserve_parser.add_argument("--output", type=Path, default=Path("zenodo_deposition_draft.json"))
    reserve_parser.add_argument("--doi-output", type=Path, default=Path("zenodo_reserved_doi.txt"))
    reserve_parser.add_argument("--dry-run", action="store_true", help="Print the API payload only.")
    reserve_parser.set_defaults(func=reserve)

    upload_parser = subparsers.add_parser("upload", help="Upload one archive file to an existing draft.")
    upload_parser.add_argument("--deposition-json", type=Path, default=Path("zenodo_deposition_draft.json"))
    upload_parser.add_argument("--file", type=Path, required=True)
    upload_parser.set_defaults(func=upload)

    publish_parser = subparsers.add_parser("publish", help="Publish the draft record.")
    publish_parser.add_argument("--deposition-json", type=Path, default=Path("zenodo_deposition_draft.json"))
    publish_parser.add_argument("--publish", action="store_true", help="Required safety flag.")
    publish_parser.set_defaults(func=publish)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ZenodoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
