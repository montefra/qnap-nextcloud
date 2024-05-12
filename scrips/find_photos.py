#!/bin/env python
import argparse as ap
import hashlib
import io
import logging
from pathlib import Path
from typing import Sequence

from attr import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ImageFile:
    path: Path
    checksum: str
    primary: bool


def parse(argv: Sequence[str] | None = None) -> ap.Namespace:
    p = ap.ArgumentParser(formatter_class=ap.ArgumentDefaultsHelpFormatter)

    p.add_argument("json_directories", type=Path)
    p.add_argument("image_directories", type=Path)

    p.add_argument("-o", "--output-file-prefix", type=str, default="json_foto_")
    p.add_argument("-p", "--plan", action="store_true")

    return p.parse_args(args=argv)


def setup_logs():
    logging.basicConfig(filename="actions.log", level=logging.INFO)


def find_files(json_file: Path, target_directory: Path) -> list[Path]:
    image_file_name = json_file.stem

    matching_files = []
    for dirpath, _, file_names in target_directory.walk():
        for file_name in file_names:
            if file_name.lower() == image_file_name.lower():
                matching_files.append(dirpath / file_name)

    return matching_files


def handle_files(
    json_file: Path,
    image_files: list[Path],
    output_file_prefix: str,
    plan: bool = False,
) -> None:
    file_count = len(image_files)
    outfile = Path(__file__).parent / f"{output_file_prefix}{file_count}.txt"

    with outfile.open(mode="a") as f:
        match file_count:
            case 0:
                handle_no_match(json_file, f, plan)
            case 1:
                handle_one_match(json_file, image_files[0], f, plan)
            case _:
                handle_multiple_matches(json_file, image_files, f, plan)
        if plan:
            f.write("====\n")


def handle_no_match(
    json_file: Path, outfile: io.TextIOBase, plan: bool = False
) -> None:
    if plan:
        outfile.write(f"{json_file}\n")
        outfile.write(f"Action: rm {json_file}\n")
    else:
        logger.info("Removing %s", json_file)
        json_file.unlink()


def handle_one_match(
    json_file: Path, image_file: Path, outfile: io.TextIOBase, plan: bool = False
) -> None:
    if plan:
        outfile.write(f"{json_file}\n")
        outfile.write(f"{image_file}\n")

    if json_file.parent == image_file.parent:
        if plan:
            outfile.write("Action: nothing to be done\n")
    else:
        if plan:
            outfile.write(f"Action: mv {image_file} {json_file.parent}\n")
        else:
            logger.info("Moving %s to %s", image_file, json_file.parent)
            image_file.rename(json_file.parent / image_file.name)


def handle_multiple_matches(
    json_file: Path,
    image_files: list[Path],
    output_file: io.TextIOBase,
    plan: bool = False,
) -> None:
    images = [
        ImageFile(f, compute_checksum(f), f.parent == json_file.parent)
        for f in image_files
    ]
    reference_image = [i for i in images if i.primary]
    has_reference_image = len(reference_image) > 0
    automatic_resolution = has_reference_image
    if has_reference_image:
        automatic_resolution = automatic_resolution & all(
            i.checksum == reference_image[0].checksum
            for i in images
            if i.path != reference_image[0].path
        )

    if plan or not has_reference_image:
        output_file.write(f"{json_file}\n")

    if automatic_resolution:
        handle_multiple_matche_automatic(reference_image[0], images, output_file, plan)
    else:
        handle_multiple_matche_manual(images, output_file)
        if not plan:
            output_file.write("====\n")


def handle_multiple_matche_automatic(
    reference_image: ImageFile,
    images: list[ImageFile],
    output_file: io.TextIOBase,
    plan: bool = False,
) -> None:
    if plan:
        output_file.write(
            f"Action: keep {reference_image.checksum} {reference_image.path}\n"
        )
    for image_file in images:
        if image_file.path != reference_image.path:
            if plan:
                output_file.write(
                    f"Action: rm {image_file.path} # {image_file.checksum}\n"
                )
            else:
                logger.info("Removing %s", image_file.path)
                image_file.path.unlink()


def handle_multiple_matche_manual(
    images: list[ImageFile], output_file: io.TextIOBase
) -> None:
    output_file.write("No reference file found or not all hash match\n")
    for image in images:
        output_file.write(f"{image.checksum} {image.path}\n")


def compute_checksum(file_path: Path) -> str:
    with file_path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main():

    p = parse()

    album_dir: Path = p.json_directories  # type: ignore

    loop_count = 0

    for dirpath, _, file_names in album_dir.walk():
        for name in file_names:
            if name.endswith(".json"):
                json_file = dirpath / name

                matching_files = find_files(json_file, p.image_directories)
                handle_files(json_file, matching_files, p.output_file_prefix, plan=p.plan)

                loop_count += 1
                if loop_count % 10 == 0:
                    print(".", end="", flush=True)

    print()
    print(f"{loop_count} json files have been processed")


if __name__ == "__main__":
    setup_logs()
    main()
