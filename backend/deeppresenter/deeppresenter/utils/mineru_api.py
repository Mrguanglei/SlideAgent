import asyncio
import os
import tempfile
import zipfile
from pathlib import Path

import aiohttp


async def parse_pdf(
    pdf_path: str, output_path: str, token: str, model_version: str = "vlm"
) -> None:
    """Parse PDF using MinerU external API

    Args:
        pdf_path: PDF file path
        output_path: Output directory
        token: API Token
        model_version: Model version (vlm/pipeline)
    """
    os.makedirs(output_path, exist_ok=True)
    pdf_path = Path(pdf_path)

    async with aiohttp.ClientSession() as session:
        batch_id, upload_url, upload_headers = await _request_upload_url(
            session, pdf_path.name, pdf_path.stem[:128], model_version, token
        )

        await _upload_file(session, upload_url, pdf_path, upload_headers)

        zip_url = await _poll_result(session, batch_id, token)

        await _download_and_extract(session, zip_url, output_path)


async def _request_upload_url(
    session: aiohttp.ClientSession,
    filename: str,
    data_id: str,
    model_version: str,
    token: str,
) -> tuple[str, str, dict[str, str] | None]:
    """Request upload URL, returns (batch_id, upload_url, upload_headers)"""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {
        "files": [{"name": filename, "data_id": data_id}],
        "model_version": model_version,
    }

    async with session.post(
        "https://mineru.net/api/v4/file-urls/batch", headers=headers, json=payload
    ) as resp:
        resp.raise_for_status()
        result = await resp.json()
        if result["code"] != 0:
            raise RuntimeError(
                f"Failed to request upload URL: {result.get('msg', 'Unknown error')}"
            )

        data = result["data"]
        upload_headers = data.get("headers", [None])[0] if "headers" in data else None
        return data["batch_id"], data["file_urls"][0], upload_headers


async def _upload_file(
    session: aiohttp.ClientSession,
    upload_url: str,
    pdf_path: Path,
    headers: dict[str, str] | None = None,
) -> None:
    """Upload PDF file to OSS"""
    file_data = pdf_path.read_bytes()

    upload_headers = headers if headers else {}

    async with session.put(
        upload_url,
        data=file_data,
        headers=upload_headers,
        skip_auto_headers={"Content-Type"},
    ) as resp:
        resp.raise_for_status()


async def _poll_result(
    session: aiohttp.ClientSession, batch_id: str, token: str
) -> str:
    """Poll parsing result, returns download URL"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"

    while True:
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            result = await resp.json()

            if result["code"] != 0:
                raise RuntimeError(
                    f"Query failed: {result.get('msg', 'Unknown error')}"
                )

            extract = result["data"]["extract_result"][0]
            state = extract["state"]

            if state == "done":
                return extract["full_zip_url"]
            elif state == "failed":
                raise RuntimeError(
                    f"Parsing failed: {extract.get('err_msg', 'Unknown error')}"
                )

            await asyncio.sleep(5)


async def _download_and_extract(
    session: aiohttp.ClientSession, zip_url: str, output_path: str
) -> None:
    """Download and extract result"""
    async with session.get(zip_url) as resp:
        resp.raise_for_status()
        content = await resp.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        tmp.write(content)
        zip_path = tmp.name

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        all_names = [name for name in zip_ref.namelist() if name.strip()]
        top_level = {name.split("/", 1)[0] for name in all_names}

        if len(top_level) == 1 and all("/" in name for name in all_names):
            prefix = list(top_level)[0] + "/"
        else:
            prefix = ""

        for member in zip_ref.infolist():
            if not member.is_dir():
                rel_path = (
                    member.filename.removeprefix(prefix) if prefix else member.filename
                )
                dest_path = os.path.join(output_path, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zip_ref.open(member) as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())

    os.unlink(zip_path)
