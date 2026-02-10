import os
import zipfile
import tarfile
from datetime import datetime
from typing import List, Union


def _get_timestamp() -> str:
    """Generate a timestamp string for unique filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def compress(
    sources: Union[str, list],
    destination: str,
    compression_type: str = "zip",
    progress_callback=None
) -> str:
    """Compress or copy files depending on the selected compression type."""
    if isinstance(sources, str):
        sources = [sources]

    if not os.path.exists(destination):
        os.makedirs(destination, exist_ok=True)

    if compression_type:
        compression_type = compression_type.lower()

    if compression_type in ["none", "", None]:
        import shutil
        import time

        processed = 0
        total_files = 0
        start_time = time.time()

        for src in sources:
            if os.path.isfile(src):
                total_files += 1
            elif os.path.isdir(src):
                for _, _, files in os.walk(src):
                    total_files += len(files)
        if total_files == 0:
            total_files = 1

        for src in sources:
            base_name = os.path.basename(src.rstrip("/\\"))
            dst_path = os.path.join(destination, base_name)

            if os.path.isdir(src):
                shutil.copytree(src, dst_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst_path)

            processed += 1
            if progress_callback:
                elapsed = time.time() - start_time
                percent = min((processed / total_files) * 100, 100)
                speed = processed / elapsed if elapsed > 0 else 0
                eta = (total_files - processed) / speed if speed > 0 else 0
                progress_callback(percent, processed, total_files, speed, eta)
                time.sleep(0.005)

        return destination

    archive_name = f"backup_{_get_timestamp()}"
    archive_path = os.path.join(destination, f"{archive_name}.{compression_type}")

    import time
    processed = 0
    start_time = time.time()

    total_files = 0
    for src in sources:
        if os.path.isfile(src):
            total_files += 1
        elif os.path.isdir(src):
            for _, _, files in os.walk(src):
                total_files += len(files)
    if total_files == 0:
        total_files = 1  

    def _update_progress(increment=1):
        nonlocal processed
        processed += increment
        if progress_callback:
            elapsed = time.time() - start_time
            percent = min((processed / total_files) * 100, 100)
            speed = processed / elapsed if elapsed > 0 else 0
            eta = (total_files - processed) / speed if speed > 0 else 0
            progress_callback(percent, processed, total_files, speed, eta)
            time.sleep(0.005)

    if compression_type == "zip":
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for src in sources:
                if os.path.isdir(src):
                    for root, _, files in os.walk(src):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(src))
                            zipf.write(file_path, arcname)
                            _update_progress()
                else:
                    zipf.write(src, os.path.basename(src))
                    _update_progress()

    elif compression_type == "tar":
        with tarfile.open(archive_path, "w") as tarf:
            for src in sources:
                tarf.add(src, arcname=os.path.basename(src))
                _update_progress()

    else:
        raise ValueError(f"Unsupported compression type: {compression_type}")

    if progress_callback:
        progress_callback(100, total_files, total_files, processed / (time.time() - start_time), 0)

    return archive_path


create_archive = compress