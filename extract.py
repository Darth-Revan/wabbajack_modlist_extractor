#!/usr/bin/env python

# wabbajack_modlist_extractor
# Copyright (C) 2025 Darth-Revan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from argparse import ArgumentParser
from pathlib import Path
from sys import exit
from shutil import which
from typing import Dict
from subprocess import run
from zipfile import ZipFile
from tempfile import TemporaryDirectory
from json import load, JSONDecodeError, dumps


MODLIST_FILENAME = "modlist"
RED   = "\033[1;31m"
BLUE  = "\033[1;34m"
RESET = "\033[0;0m"


def error(message: str, do_exit: bool = True):
    print(RED, f"[-] {message}", RESET)
    if do_exit:
        exit(1)


def info(message: str):
    print(BLUE, f"[*] {message}", RESET)


class ModInfo:

    def __init__(self, data: Dict):
        state = data.get("State", None)
        if not state:
            raise AttributeError("The entry does not contain a State object")

        etype = state.get("$type", None)
        if not etype:
            raise AttributeError("The entry does not contain a type")

        if not "NexusDownloader" in etype:
            raise ValueError(f"Unsupported download type {etype}")

        self.name = state.get("Name", None)
        self.author = state.get("Author", None)
        self.file_id = state.get("FileID", None)
        self.mod_id = state.get("ModID", None)
        self.game = state.get("GameName", None)

        if any(v is None for v in (self.name, self.author, self.file_id, self.mod_id, self.game)):
            print(state)
            raise AttributeError("The entry is missing a required attribute")

    @property
    def url(self) -> str:
        return f"https://www.nexusmods.com/{self.game}/mods/{self.mod_id}?tab=files&file_id={self.file_id}"

    @property
    def mod_url(self) -> str:
        return f"https://www.nexusmods.com/{self.game}/mods/{self.mod_id}"

    def __str__(self) -> str:
        return f"\"{self.name}\" by {self.author}"


if __name__ == "__main__":
    parser = ArgumentParser(prog="extract", description="Small script to extract mod URLs from a Wabbajack modlist")
    parser.add_argument("INPUT", action="store", type=Path, help="The input Wabbajack file")
    parser.add_argument("OUTPUT", action="store", type=Path, help="The output file")
    parser.add_argument(
        "-m", "--mods", action="store_true", dest="use_mods",
        help="Use the base mod URL instead of the target file URL"
    )
    parsed = parser.parse_args()

    if not parsed.INPUT.is_file():
        error("The input file does not exist")

    if parsed.OUTPUT.is_file():
        error("The output file does already exist")

    if not which("file"):
        error("The file command is not available")

    info(f"Trying to use file {parsed.INPUT}")
    parsed.INPUT.resolve(strict=True)

    proc = run(["file", str(parsed.INPUT)], capture_output=True)
    if proc.returncode != 0:
        error("Executing the file command failed")

    if not "Zip archive data" in proc.stdout.decode("ascii"):
        error("The input file does not look like a ZIP file")

    info("Successfully checked requirements")

    modlist_path = Path()
    with TemporaryDirectory(prefix=parser.prog) as tempd:
        with ZipFile(parsed.INPUT, "r") as inf:
            modlist = list(filter(lambda x: x.filename == MODLIST_FILENAME, inf.filelist))
            if not modlist:
                error("The input file does not contain a modlist file")

            if len(modlist) > 1:
                error("Got more than one modlist file")

            inf.extract(modlist[0], path=tempd)
            modlist_path = Path(tempd).joinpath(MODLIST_FILENAME)

        if not modlist_path.is_file():
            error("The extracted modlist file does not exist anymore")

        proc = run(["file", str(modlist_path)], capture_output=True)
        if proc.returncode != 0:
            error("Executing the file command failed")

        if not "ASCII text" in proc.stdout.decode("ascii"):
            error("The modlist file does not look like a text file")

        data = dict()
        with open(modlist_path, "r", encoding="UTF-8") as inf:
            try:
                data = load(inf)
            except JSONDecodeError as e:
                error(f"Failed to parse modlists: {e}")

        if not data:
            error("Failed to load data from modlist")

        info("Successfully parsed modlist")

        with open("temp", "w") as outf:
            outf.write(dumps(data, indent=4))

        archives = data.get("Archives", None)
        if archives is None:
            error("Failed to get archives data from modlist")

        if not archives:
            error("No archives defined in modlist")

        info(f"Got {len(archives)} in modlist")
        output = list()
        # output = [ModInfo(entry) for entry in archives]
        for i, e in enumerate(archives):
            try:
                output.append(ModInfo(e))
            except ValueError as e:
                error(f"Error for entry {i}: {e}", do_exit=False)
            except AttributeError as e:
                error(f"Error for entry {i}: {e}", do_exit=False)
                continue

        with open(parsed.OUTPUT, "w") as outf:
            for entry in output:
                if parsed.use_mods:
                    outf.write(f"## '{entry.name}' by {entry.author}\n{entry.mod_url}\n\n")
                else:
                    outf.write(f"## '{entry.name}' by {entry.author}\n{entry.url}\n\n")
