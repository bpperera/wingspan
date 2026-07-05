"""Import Wingspan Americas birds from the official bird-list PDF into wingspan_game.csv."""

from __future__ import annotations

import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parent
PDF_PATH = ROOT / "bird-list-americas-20260125-a4.pdf"
CSV_PATH = ROOT / "wingspan_game.csv"
WINGSEARCH_URL = (
    "https://raw.githubusercontent.com/navarog/wingsearch/master/src/assets/data/master.json"
)

COLOR_MAP = {
    "brown": "Brown",
    "white": "White",
    "teal": "Teal",
    "pink": "Pink",
    "yellow": "Yellow",
}

BONUS_COLUMNS = [
    "Anatomist",
    "Cartographer",
    "Historian",
    "Photographer",
    "Backyard Birder",
    "Bird Bander",
    "Bird Counter",
    "Bird Feeder",
    "Diet Specialist",
    "Enclosure Builder",
    "Falconer",
    "Fishery Manager",
    "Food Web Expert",
    "Forester",
    "Large Bird Specialist",
    "Nest Box Builder",
    "Omnivore Expert",
    "Passerine Specialist",
    "Platform Builder",
    "Prairie Manager",
    "Rodentologist",
    "Viticulturalist",
    "Wetland Scientist",
    "Wildlife Gardener",
    "Caprimulgiform Specialist",
    "Small Clutch Specialist",
    "Endangered Species Protector",
]

PDF_COLUMNS = {
    "name_end": 240,
    "forest": (240, 258),
    "grassland": (258, 276),
    "wetland": (276, 288),
    "vp": (288, 318),
    "wingspan": (375, 405),
    "power": 405,
}


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_pdf_birds(pdf_path: Path) -> list[dict[str, object]]:
    birds: list[dict[str, object]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            rows: dict[int, list[dict[str, object]]] = defaultdict(list)
            for char in page.chars:
                y = round(char["top"] / 2) * 2
                rows[y].append(char)

            for chars in rows.values():
                if not any(char["x0"] < PDF_COLUMNS["name_end"] for char in chars):
                    continue

                name_chars = sorted(
                    (char for char in chars if char["x0"] < PDF_COLUMNS["name_end"]),
                    key=lambda char: char["x0"],
                )
                name = "".join(char["text"] for char in name_chars).strip()
                name = name.replace("ﬁ", "fi")
                name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
                name = re.sub(r"\s+-\s+", "-", name).strip()
                if not name or name.lower().replace(" ", "") == "commonname":
                    continue
                if not name[0].isupper():
                    continue

                vp_chars = sorted(
                    (
                        char
                        for char in chars
                        if PDF_COLUMNS["vp"][0] <= char["x0"] < PDF_COLUMNS["vp"][1]
                    ),
                    key=lambda char: char["x0"],
                )
                vp = "".join(char["text"] for char in vp_chars).strip()
                if not vp.isdigit():
                    continue

                ws_chars = sorted(
                    (
                        char
                        for char in chars
                        if PDF_COLUMNS["wingspan"][0] <= char["x0"] < PDF_COLUMNS["wingspan"][1]
                    ),
                    key=lambda char: char["x0"],
                )
                wingspan = "".join(char["text"] for char in ws_chars).strip()
                if wingspan == "*":
                    wingspan_value: object = "*"
                elif wingspan.isdigit():
                    wingspan_value = int(wingspan)
                else:
                    continue

                birds.append(
                    {
                        "Common name": name,
                        "Victory points": int(vp),
                        "Wingspan": wingspan_value,
                        "Forest": "X" if has_plus(chars, PDF_COLUMNS["forest"]) else "",
                        "Grassland": "X" if has_plus(chars, PDF_COLUMNS["grassland"]) else "",
                        "Wetland": "X" if has_plus(chars, PDF_COLUMNS["wetland"]) else "",
                    }
                )

    return birds


def has_plus(chars: list[dict[str, object]], bounds: tuple[int, int]) -> bool:
    return any(
        char["text"] == "+" and bounds[0] <= char["x0"] < bounds[1]
        for char in chars
    )


def load_wingsearch_americas() -> list[dict[str, object]]:
    with urllib.request.urlopen(WINGSEARCH_URL) as response:
        birds = json.load(response)
    return [bird for bird in birds if bird.get("Set") == "americas"]


def mark(value: object) -> str:
    return "X" if value == "X" else ""


def numeric_or_empty(value: object) -> object:
    if value in (None, "", 0, 0.0):
        return pd.NA
    if value == "*":
        return "*"
    return int(value) if float(value).is_integer() else value


def nest_type(value: object) -> str:
    if not value or pd.isna(value):
        return ""
    return str(value).strip().title()


def values_equal(left: object, right: object) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    if pd.isna(left) or pd.isna(right):
        return False
    return left == right


def flatten_rulings(bird: dict[str, object], row: dict[str, object]) -> None:
    for prefix, key in (("additionalRulings", "additionalRulings"), ("rulings", "rulings")):
        entries = bird.get(key) or []
        for index, entry in enumerate(entries):
            row[f"{prefix}/{index}/text"] = entry.get("text", "")
            row[f"{prefix}/{index}/source"] = entry.get("source", "")


def wingsearch_to_csv_row(bird: dict[str, object], columns: list[str]) -> dict[str, object]:
    row = {column: pd.NA for column in columns}
    row["Common name"] = bird.get("Common name", "")
    row["Scientific name"] = bird.get("Scientific name", "")
    row["Expansion"] = "americas"
    row["Color"] = COLOR_MAP.get(str(bird.get("Color", "")).lower(), "")
    row["PowerCategory"] = pd.NA
    row["Power text"] = bird.get("Power text", "")
    row["Predator"] = mark(bird.get("Predator"))
    row["Flocking"] = mark(bird.get("Flocking"))
    row["Bonus card"] = mark(bird.get("Bonus card"))
    row["Victory points"] = numeric_or_empty(bird.get("Victory points"))
    row["Nest type"] = nest_type(bird.get("Nest type"))
    row["Egg capacity"] = numeric_or_empty(bird.get("Egg limit"))
    row["Wingspan"] = numeric_or_empty(bird.get("Wingspan"))
    row["Forest"] = mark(bird.get("Forest"))
    row["Grassland"] = mark(bird.get("Grassland"))
    row["Wetland"] = mark(bird.get("Wetland"))

    for food in [
        "Invertebrate",
        "Seed",
        "Fish",
        "Fruit",
        "Rodent",
        "Nectar",
        "Wild (food)",
    ]:
        row[food] = numeric_or_empty(bird.get(food))

    row["/ (food cost)"] = mark(bird.get("/ (food cost)"))
    row["* (food cost)"] = mark(bird.get("* (food cost)"))
    row["Total food cost"] = numeric_or_empty(bird.get("Total food cost"))

    for bonus in BONUS_COLUMNS:
        row[bonus] = mark(bird.get(bonus))

    beak = str(bird.get("Beak direction", "")).upper()
    row["Beak Pointing Left"] = "X" if beak == "L" else ""
    row["Beak Pointing Right"] = "X" if beak == "R" else ""
    row["Note"] = bird.get("Note", "")
    row["id"] = int(bird["id"])
    flatten_rulings(bird, row)
    return row


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Missing PDF: {PDF_PATH}")

    pdf_birds = parse_pdf_birds(PDF_PATH)
    wingsearch_birds = load_wingsearch_americas()
    existing = pd.read_csv(CSV_PATH)

    pdf_by_name = {normalize_name(bird["Common name"]): bird for bird in pdf_birds}
    ws_by_name = {normalize_name(bird["Common name"]): bird for bird in wingsearch_birds}

    missing_in_ws = sorted(set(pdf_by_name) - set(ws_by_name))
    missing_in_pdf = sorted(set(ws_by_name) - set(pdf_by_name))
    if missing_in_ws:
        raise RuntimeError(f"PDF birds missing from structured source: {missing_in_ws[:5]}")
    if missing_in_pdf:
        raise RuntimeError(f"Structured birds missing from PDF: {missing_in_pdf[:5]}")

    already_present = existing[
        existing["Expansion"].astype(str).str.lower() == "americas"
    ]
    if len(already_present):
        print(f"Removing {len(already_present)} existing americas rows before re-import.")
        existing = existing[existing["Expansion"].astype(str).str.lower() != "americas"]

    new_rows = []
    mismatches = []
    for bird in wingsearch_birds:
        pdf_bird = pdf_by_name[normalize_name(bird["Common name"])]
        for field in ("Victory points", "Wingspan", "Forest", "Grassland", "Wetland"):
            pdf_value = pdf_bird[field]
            if field in {"Forest", "Grassland", "Wetland"}:
                ws_value = mark(bird.get(field))
            else:
                ws_value = numeric_or_empty(bird.get(field))

            pdf_cmp = pd.NA if pdf_value in ("", None) else pdf_value
            ws_cmp = pd.NA if ws_value is pd.NA or (isinstance(ws_value, float) and pd.isna(ws_value)) else ws_value
            if not values_equal(pdf_cmp, ws_cmp):
                mismatches.append((bird["Common name"], field, pdf_value, ws_value))

        new_rows.append(wingsearch_to_csv_row(bird, existing.columns.tolist()))

    if mismatches:
        print(f"Warning: {len(mismatches)} PDF vs structured mismatches (using structured data).")
        for item in mismatches[:5]:
            print(" ", item)

    americas_df = pd.DataFrame(new_rows, columns=existing.columns)
    combined = pd.concat([existing, americas_df], ignore_index=True)
    combined.to_csv(CSV_PATH, index=False)

    print(f"Parsed {len(pdf_birds)} birds from PDF.")
    print(f"Added {len(americas_df)} americas birds to {CSV_PATH.name}.")
    print(f"Total birds in dataset: {len(combined)}.")


if __name__ == "__main__":
    main()
