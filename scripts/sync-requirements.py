#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script performs two tasks:
 * It updates the ``requirements.txt`` file with the packages found in the ``Pipfile``.
 * It reformats the ``Pipfile`` to my opinionated standards.
"""
from __future__ import annotations

import difflib
import os
from itertools import filterfalse, starmap
from typing import Any, Callable, Hashable, Tuple, Union

import click  # noqa: I900
from packaging.utils import canonicalize_name  # noqa: I900
from requirementslib import Requirement  # noqa: I900
from tomlkit import loads  # noqa: I900
from tomlkit.container import Container  # noqa: I900
from tomlkit.items import AoT, Key, KeyType, Table, Trivia  # noqa: I900
from tomlkit.toml_document import TOMLDocument  # noqa: I900

PathLike = Union[bytes, str, os.PathLike]
MaybeKey = Union[str, Key]
ContainerItem = Tuple[MaybeKey, Any]

ROOT_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))
ROOT_REQUIREMENTS = os.path.join(ROOT_PATH, "requirements.txt")
ROOT_PIPFILE = os.path.join(ROOT_PATH, "Pipfile")
PIPFILE_SECTIONS = ("source", "packages", "dev-packages", "requires", "scripts")
DEFAULT_SOURCE = (
    ("name", "pypi"),
    ("url", "https://pypi.org/simple"),
    ("verify_ssl", True),
)


def unwrap_key(key: MaybeKey) -> str:
    if isinstance(key, Key):
        return key.key

    return key


def reorder_container(
    container: Container,
    sort_key: Callable[[ContainerItem], Hashable] = None,
    reverse: bool = False,
    key_type: KeyType = None,
) -> None:
    items = container._body
    if sort_key is not None or reverse:
        items.sort(key=sort_key, reverse=reverse)

    container._map = {}
    container._body = []

    for key, value in items:
        if key is None:
            pass
        elif isinstance(key, Key):
            if key_type is not None:
                key = Key(key.key, key_type)
        else:
            key = Key(key, key_type)

        container.append(key, value)


def pipfile_source_key(pair):
    not_found = len(DEFAULT_SOURCE)

    key, value = pair
    if key is None:
        return (not_found + 1, key)

    key = unwrap_key(key)
    norm = key.lower()
    for idx, (key, _) in enumerate(DEFAULT_SOURCE):
        if norm == key:
            return (idx, key)

    return (not_found, key)


def pipfile_section_key(pair):
    not_found = len(PIPFILE_SECTIONS)

    key, value = pair
    if key is None:
        return (not_found + 1, None, None)

    key = unwrap_key(key)
    normalized = key.lower().replace("_", "-")

    try:
        idx = PIPFILE_SECTIONS.index(normalized)
    except ValueError:
        idx = not_found

    return (idx, normalized, key)


def pipfile_packages_key(pair):
    key, value = pair
    key = unwrap_key(key)
    return (key is None, canonicalize_name(key) if key else None)


def requirement_sort_key(item: Requirement) -> Hashable:
    return (item.is_named, item.normalized_name)


def is_default(source):
    return all(source.get(k) == v for (k, v) in DEFAULT_SOURCE)


def load_pipfile(path: PathLike = None) -> TOMLDocument:
    if path is None:
        path = ROOT_PIPFILE

    with open(path, "r") as fp:
        doc = loads(fp.read())
    doc._parsed = True

    sources = []
    have_default = False
    for key in ("source", "sources"):
        try:
            item = doc.item(key)
        except KeyError:
            continue

        doc.remove(key)

        if isinstance(item, AoT):
            items = item.body
        else:
            items = item.value

        for source in items:
            if not isinstance(source, Table):
                source = Table(source, Trivia(trail=""), is_aot_element=True)
            container = source.value
            reorder_container(container, pipfile_source_key, key_type=KeyType.Basic)
            if not have_default and is_default(container):
                have_default = True

            sources.append(source)

    if not have_default:
        source = Table(Container(True), Trivia(), True)
        for k, v in DEFAULT_SOURCE:
            source.append(k, v)

        sources.insert(0, source)

    doc.append("source", AoT(sources, parsed=True))
    return doc


def update_requirements(path: PathLike, pipfile: TOMLDocument) -> None:
    sources = list(filterfalse(is_default, pipfile.get("source", [])))
    packages = pipfile.get("packages", {})
    requirements = list(starmap(Requirement.from_pipfile, packages.items()))
    requirements.sort(key=requirement_sort_key)
    lines = [r.as_line(sources) + os.linesep for r in requirements]

    with open(path, "w") as fp:
        fp.writelines(lines)


def dump_pipfile(path: PathLike, pipfile: TOMLDocument) -> None:
    reorder_container(pipfile, pipfile_section_key, key_type=KeyType.Bare)

    for name in ("packages", "dev-packages"):
        try:
            section = pipfile.item(name)
        except KeyError:
            pass
        else:
            container = section.value
            reorder_container(container, pipfile_packages_key, key_type=KeyType.Basic)

    value = pipfile.as_string()
    try:
        with open(path, "r") as fp:
            old_value = fp.read()
    except OSError:
        old_value = ""

    if value != old_value:
        diff = difflib.ndiff(old_value.splitlines(True), value.splitlines(True))
        print("".join(diff), end="")

        with open(path, "w") as fp:
            fp.write(value)


@click.command()
@click.option(
    "-r",
    "--requirements-file",
    default=ROOT_REQUIREMENTS,
    help="Specify the requirements.txt file to update.",
    show_default=True,
    show_envvar=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.option(
    "--skip-requirements-file",
    help="Skip updating the requirements file.",
    is_flag=True,
    show_envvar=True,
)
@click.option(
    "-p",
    "--pipfile",
    default=ROOT_PIPFILE,
    help="Specify the Pipfile to read and optionally update.",
    show_default=True,
    show_envvar=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.option(
    "--skip-pipfile",
    is_flag=True,
    help="Skip reformatting the Pipfile.",
    show_envvar=True,
)
def main(requirements_file, skip_requirements_file, pipfile, skip_pipfile):
    """Update the requirements.txt file and reformat the Pipfile."""
    pf = load_pipfile(pipfile)

    if not skip_requirements_file:
        update_requirements(requirements_file, pf)

    if not skip_pipfile:
        dump_pipfile(pipfile, pf)


if __name__ == "__main__":
    main(auto_envvar_prefix="SHIELDS")
