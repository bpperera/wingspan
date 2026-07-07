from __future__ import annotations

from math import comb
from typing import Literal

import altair as alt
import pandas as pd
import streamlit as st

DATA_PATH = "wingspan_game.csv"

EXPANSION_LABELS = {
    "originalcore": "Original",
    "european": "European",
    "oceania": "Oceania",
    "asia": "Asia",
    "americas": "Americas",
    "swiftstart": "Swift",
}

HABITAT_COLUMNS = ["Forest", "Grassland", "Wetland"]
FOOD_COLUMNS = [
    "Invertebrate",
    "Seed",
    "Fish",
    "Fruit",
    "Rodent",
    "Nectar",
    "Wild (food)",
]
MARKER_COLUMNS = ["Predator", "Flocking", "Bonus card"]
BONUS_CARD_COLUMNS = [
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
    "Beak Pointing Left",
    "Beak Pointing Right",
]

DISPLAY_COLUMNS = [
    "Common name",
    "Expansion",
    "Victory points",
    "Total food cost",
    "Nest type",
    "Color",
    "PowerCategory",
    "Forest",
    "Grassland",
    "Wetland",
]

# Each Wingspan die has 6 equally likely faces; the wild face counts as invertebrate or seed.
DIE_FACE_OPTIONS: list[frozenset[str]] = [
    frozenset({"Fish"}),
    frozenset({"Rodent"}),
    frozenset({"Fruit"}),
    frozenset({"Invertebrate"}),
    frozenset({"Seed"}),
    frozenset({"Invertebrate", "Seed"}),
]
DICE_FOODS = ["Invertebrate", "Seed", "Fish", "Fruit", "Rodent"]


@st.cache_data
def load_birds(path: str = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["Expansion"] = df["Expansion"].astype(str)
    return df


def is_marked(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.upper().eq("X")


def prob_at_least_one(total: int, matching: int, draws: int) -> float:
    if draws <= 0 or matching <= 0:
        return 0.0
    if draws >= total:
        return 1.0
    if total - matching < draws:
        return 1.0
    return 1.0 - comb(total - matching, draws) / comb(total, draws)


def expected_matches(total: int, matching: int, draws: int) -> float:
    if total <= 0 or draws <= 0:
        return 0.0
    return draws * matching / total


def render_tri_state_filter(
    label: str,
    key: str,
) -> Literal["any", "yes", "no"]:
    return st.selectbox(
        label,
        options=["Any", "Yes", "No"],
        index=0,
        key=key,
    ).lower()


def apply_marker_filter(
    df: pd.DataFrame,
    column: str,
    choice: Literal["any", "yes", "no"],
) -> pd.DataFrame:
    if choice == "any":
        return df
    marked = is_marked(df[column])
    return df[marked] if choice == "yes" else df[~marked]


def apply_habitat_filter(
    df: pd.DataFrame,
    habitats: list[str],
    mode: Literal["any", "all"],
) -> pd.DataFrame:
    if not habitats:
        return df

    masks = [is_marked(df[habitat]) for habitat in habitats]
    if mode == "all":
        combined = masks[0]
        for mask in masks[1:]:
            combined &= mask
    else:
        combined = masks[0]
        for mask in masks[1:]:
            combined |= mask
    return df[combined]


def apply_bonus_filter(df: pd.DataFrame, selected_bonus: list[str]) -> pd.DataFrame:
    if not selected_bonus:
        return df

    mask = pd.Series(False, index=df.index)
    for column in selected_bonus:
        mask |= is_marked(df[column])
    return df[mask]


def apply_food_filter(
    df: pd.DataFrame,
    selected_food: list[str],
    min_cost: int | None,
) -> pd.DataFrame:
    filtered = df
    if selected_food:
        mask = pd.Series(False, index=df.index)
        for column in selected_food:
            mask |= pd.to_numeric(df[column], errors="coerce").fillna(0).gt(0)
        filtered = filtered[mask]
    if min_cost is not None:
        filtered = filtered[pd.to_numeric(filtered["Total food cost"], errors="coerce") >= min_cost]
    return filtered


def is_unlisted_wingspan(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().eq("*")


def apply_wingspan_filter(
    df: pd.DataFrame,
    ws_min: int,
    ws_max: int,
    unlisted: Literal["any", "yes", "no"],
) -> pd.DataFrame:
    numeric = pd.to_numeric(df["Wingspan"], errors="coerce")
    in_range = numeric.between(ws_min, ws_max, inclusive="both")
    unlisted_bird = is_unlisted_wingspan(df["Wingspan"])

    if unlisted == "yes":
        return df[unlisted_bird]
    if unlisted == "no":
        return df[in_range.fillna(False)]
    return df[in_range.fillna(False) | unlisted_bird]


def format_pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def build_victory_points_chart(deck: pd.DataFrame, filtered: pd.DataFrame) -> alt.Chart:
    matching_ids = set(filtered.index)
    rows: list[dict[str, object]] = []

    for vp, group in deck.groupby("Victory points", sort=True):
        total = len(group)
        matching = int(group.index.isin(matching_ids).sum())
        non_matching = total - matching
        pct_matching = 100 * matching / total if total else 0.0
        pct_label = f"{pct_matching:.0f}%"

        rows.append(
            {
                "Victory points": str(int(vp)),
                "Category": "Matching",
                "Count": matching,
                "pct_label": pct_label,
                "stack_total": total,
            }
        )
        rows.append(
            {
                "Victory points": str(int(vp)),
                "Category": "Non-matching",
                "Count": non_matching,
                "pct_label": pct_label,
                "stack_total": total,
            }
        )

    chart_df = pd.DataFrame(rows)

    bars = alt.Chart(chart_df).mark_bar().encode(
        x=alt.X("Victory points:O", title="Victory points", sort=None),
        y=alt.Y("Count:Q", stack="zero", title="Birds"),
        color=alt.Color(
            "Category:N",
            title=None,
            scale=alt.Scale(
                domain=["Matching", "Non-matching"],
                range=["#27ae60", "#bdc3c7"],
            ),
        ),
        order=alt.Order("Category", sort="ascending"),
        tooltip=[
            alt.Tooltip("Victory points:O", title="Victory points"),
            alt.Tooltip("Category:N", title="Category"),
            alt.Tooltip("Count:Q", title="Birds"),
        ],
    )

    segment_labels = (
        alt.Chart(chart_df)
        .transform_filter(alt.datum.Count > 0)
        .transform_stack(
            as_=["y0", "y1"],
            stack="Count",
            groupby=["Victory points"],
            sort=[alt.SortField("Category", order="ascending")],
        )
        .transform_calculate(label_y="(datum.y0 + datum.y1) / 2")
        .mark_text(baseline="middle", color="white", fontSize=16, fontWeight="bold")
        .encode(
            x=alt.X("Victory points:O", axis=alt.Axis(titleFontSize=16, labelFontSize=14)),
            y=alt.Y("label_y:Q", axis=alt.Axis(titleFontSize=16, labelFontSize=14)),
            text=alt.Text("Count:Q"),
            detail="Category:N",
        )
   
    )

    pct_labels = (
        alt.Chart(chart_df.drop_duplicates("Victory points"))
        .mark_text(dy=-10, fontSize=16, fontWeight="bold", color="#2c3e50")
        .encode(
            x="Victory points:O",
            y=alt.Y("stack_total:Q"),
            text="pct_label:N",
        )
    )

    return (bars + segment_labels + pct_labels).properties(height=340)


WINGSPAN_BIN_SIZE = 25


def wingspan_bin_label(wingspan: int, bin_size: int = WINGSPAN_BIN_SIZE) -> str:
    bin_start = (wingspan // bin_size) * bin_size
    return f"{bin_start}-{bin_start + bin_size - 1}"


def deck_with_numeric_wingspan(deck: pd.DataFrame) -> pd.DataFrame:
    numeric = pd.to_numeric(deck["Wingspan"], errors="coerce")
    result = deck[numeric.notna()].copy()
    result["_wingspan"] = numeric[numeric.notna()].astype(int)
    return result


def wingspan_bin_start(bin_label: str) -> int:
    return int(bin_label.split("-")[0])


def wingspan_x_encoding(bin_order: list[str]) -> alt.X:
    return alt.X(
        "Wingspan (cm):O",
        title="Wingspan (cm)",
        sort=bin_order,
    )


def build_wingspan_chart(
    deck: pd.DataFrame,
    filtered: pd.DataFrame,
    bin_size: int = WINGSPAN_BIN_SIZE,
) -> alt.Chart:
    matching_ids = set(filtered.index)
    numeric_deck = deck_with_numeric_wingspan(deck)
    numeric_deck["_bin"] = numeric_deck["_wingspan"].map(
        lambda ws: wingspan_bin_label(ws, bin_size)
    )

    bin_order = sorted(
        numeric_deck["_bin"].unique(),
        key=lambda label: int(label.split("-")[0]),
    )

    rows: list[dict[str, object]] = []
    for bin_label in bin_order:
        group = numeric_deck[numeric_deck["_bin"] == bin_label]
        total = len(group)
        matching = int(group.index.isin(matching_ids).sum())
        non_matching = total - matching
        pct_matching = 100 * matching / total if total else 0.0
        pct_label = f"{pct_matching:.0f}%"
        bin_start = wingspan_bin_start(bin_label)

        rows.append(
            {
                "Wingspan (cm)": bin_label,
                "bin_start": bin_start,
                "Category": "Matching",
                "Count": matching,
                "pct_label": pct_label,
                "stack_total": total,
            }
        )
        rows.append(
            {
                "Wingspan (cm)": bin_label,
                "bin_start": bin_start,
                "Category": "Non-matching",
                "Count": non_matching,
                "pct_label": pct_label,
                "stack_total": total,
            }
        )

    chart_df = pd.DataFrame(rows)
    chart_df["Wingspan (cm)"] = pd.Categorical(
        chart_df["Wingspan (cm)"],
        categories=bin_order,
        ordered=True,
    )

    x_axis = wingspan_x_encoding(bin_order)

    bars = alt.Chart(chart_df).mark_bar().encode(
        x=x_axis,
        y=alt.Y("Count:Q", stack="zero", title="Birds"),
        color=alt.Color(
            "Category:N",
            title=None,
            scale=alt.Scale(
                domain=["Matching", "Non-matching"],
                range=["#27ae60", "#bdc3c7"],
            ),
        ),
        order=alt.Order("Category", sort="ascending"),
        tooltip=[
            alt.Tooltip("Wingspan (cm):O", title="Wingspan (cm)"),
            alt.Tooltip("Category:N", title="Category"),
            alt.Tooltip("Count:Q", title="Birds"),
        ],
    )

    segment_labels = (
        alt.Chart(chart_df)
        .transform_filter(alt.datum.Count > 0)
        .transform_stack(
            as_=["y0", "y1"],
            stack="Count",
            groupby=["Wingspan (cm)"],
            sort=[alt.SortField("Category", order="ascending")],
        )
        .transform_calculate(label_y="(datum.y0 + datum.y1) / 2")
        .mark_text(baseline="middle", color="white", fontSize=14, fontWeight="bold")
        .encode(
            x=x_axis,
            y="label_y:Q",
            text=alt.Text("Count:Q"),
            detail="Category:N",
        )
    )

    pct_labels = (
        alt.Chart(chart_df.drop_duplicates(subset=["Wingspan (cm)"], keep="first"))
        .mark_text(dy=-10, fontSize=12, fontWeight="bold", color="#2c3e50")
        .encode(
            x=x_axis,
            y=alt.Y("stack_total:Q"),
            text="pct_label:N",
        )
    )

    return (bars + segment_labels + pct_labels).properties(height=340)


def build_wingspan_boxplot(deck: pd.DataFrame, filtered: pd.DataFrame) -> alt.Chart:
    matching_ids = set(filtered.index)
    points_df = deck_with_numeric_wingspan(deck).copy()
    points_df["Category"] = points_df.index.map(
        lambda index: "Matching" if index in matching_ids else "Non-matching"
    )
    points_df["Expansion label"] = points_df["Expansion"].map(
        lambda expansion: EXPANSION_LABELS.get(str(expansion), str(expansion))
    )

    color_scale = alt.Scale(
        domain=["Matching", "Non-matching"],
        range=["#27ae60", "#bdc3c7"],
    )
    base = alt.Chart(points_df)

    boxes = base.mark_boxplot(size=50, extent="min-max").encode(
        x=alt.X("Category:N", title=None),
        y=alt.Y("Wingspan:Q", title="Wingspan (cm)", scale=alt.Scale(zero=False)),
        color=alt.Color("Category:N", scale=color_scale, legend=None),
    )

    dots = (
        base.transform_calculate(jitter="(random() - 0.5) * 0.25")
        .mark_circle(size=45, opacity=0.6)
        .encode(
            x=alt.X("Category:N", scale=alt.Scale(padding=0.3)),
            xOffset=alt.XOffset("jitter:Q"),
            y="Wingspan:Q",
            color=alt.Color("Category:N", scale=color_scale, legend=None),
            tooltip=[
                alt.Tooltip("Common name:N", title="Bird"),
                alt.Tooltip("Wingspan:Q", title="Wingspan (cm)", format=".0f"),
                alt.Tooltip("Victory points:Q", title="Victory points", format=".0f"),
                alt.Tooltip("Expansion label:N", title="Expansion"),
                alt.Tooltip("Category:N", title="Filter match"),
            ],
        )
    )

    return (boxes + dots).properties(height=380)


def prob_die_shows_food(selected_foods: set[str]) -> float:
    if not selected_foods:
        return 0.0
    matching_faces = sum(1 for face in DIE_FACE_OPTIONS if face & selected_foods)
    return matching_faces / len(DIE_FACE_OPTIONS)


def prob_binomial_at_least(k: int, n: int, p: float) -> float:
    if k <= 0:
        return 1.0
    if n <= 0 or p <= 0:
        return 0.0
    if k > n:
        return 0.0
    return sum(
        comb(n, i) * (p**i) * ((1 - p) ** (n - i))
        for i in range(k, n + 1)
    )


def prob_at_least_one_roll_succeeds(p_per_roll: float, num_rolls: int) -> float:
    if num_rolls <= 0:
        return 0.0
    if p_per_roll >= 1:
        return 1.0
    if p_per_roll <= 0:
        return 0.0
    return 1 - (1 - p_per_roll) ** num_rolls


def prob_all_rolls_succeed(p_per_roll: float, num_rolls: int) -> float:
    if num_rolls <= 0:
        return 0.0
    if p_per_roll <= 0:
        return 0.0
    if p_per_roll >= 1:
        return 1.0
    return p_per_roll**num_rolls


def build_dice_match_chart(n_dice: int, p_die: float) -> alt.Chart:
    rows = []
    for matches in range(n_dice + 1):
        prob = comb(n_dice, matches) * (p_die**matches) * ((1 - p_die) ** (n_dice - matches))
        rows.append({"Matching dice": str(matches), "Probability": prob})

    chart_df = pd.DataFrame(rows)
    return (
        alt.Chart(chart_df)
        .mark_bar(color="#3498db")
        .encode(
            x=alt.X("Matching dice:O", title="Matching dice on one roll", sort=None),
            y=alt.Y("Probability:Q", axis=alt.Axis(format="%"), title="Probability"),
            tooltip=[
                alt.Tooltip("Matching dice:O", title="Matching dice"),
                alt.Tooltip("Probability:Q", title="Probability", format=".1%"),
            ],
        )
        .properties(height=280)
    )


def render_dice_tab() -> None:
    st.subheader("Food dice probability")
    st.caption(
        "Models standard Wingspan dice: each die has fish, rodent, fruit, invertebrate, "
        "seed, and one wild invertebrate/seed face. Each die roll is independent."
    )

    left, right = st.columns([1, 1])

    with left:
        selected_foods = st.multiselect(
            "Food required",
            options=DICE_FOODS,
            default=["Rodent"],
            help="A die counts as a match if it shows any selected food. "
            "The wild face counts for invertebrate or seed.",
        )
        dice_per_roll = st.number_input(
            "Dice rolled per attempt",
            min_value=1,
            max_value=5,
            value=2,
            help="How many dice you roll in one attempt (e.g. hunting rolls dice not in the birdfeeder).",
        )
        num_rolls = st.number_input(
            "Number of roll attempts",
            min_value=1,
            max_value=10,
            value=1,
            help="How many separate times you roll. Attempts are independent.",
        )
        min_matches = st.number_input(
            "Minimum matching dice per attempt",
            min_value=1,
            max_value=int(dice_per_roll),
            value=1,
            help="An attempt succeeds if at least this many dice show the required food.",
        )

    if not selected_foods:
        st.warning("Select at least one food type.")
        return

    p_die = prob_die_shows_food(set(selected_foods))
    p_per_roll = prob_binomial_at_least(min_matches, int(dice_per_roll), p_die)
    p_at_least_one = prob_at_least_one_roll_succeeds(p_per_roll, int(num_rolls))
    p_all_success = prob_all_rolls_succeed(p_per_roll, int(num_rolls))
    p_all_fail = 1 - p_at_least_one

    with right:
        st.markdown("**Per-die odds**")
        face_rows = []
        for food in DICE_FOODS:
            face_rows.append(
                {
                    "Food": food,
                    "P(single die)": prob_die_shows_food({food}),
                }
            )
        face_df = pd.DataFrame(face_rows)
        face_df["P(single die)"] = face_df["P(single die)"].map(format_pct)
        st.dataframe(face_df, hide_index=True, use_container_width=True)

    st.markdown("**Probabilities**")
    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Single die matches",
        format_pct(p_die),
        help="One die lands on a face that satisfies your required food.",
    )
    m2.metric(
        f"One attempt succeeds (≥{min_matches} of {dice_per_roll} dice)",
        format_pct(p_per_roll),
        help="You roll once and meet the minimum number of matching dice.",
    )
    m3.metric(
        "One attempt fails",
        format_pct(1 - p_per_roll),
        help="You roll once and do not meet the minimum number of matching dice.",
    )

    m4, m5, m6 = st.columns(3)
    m4.metric(
        f"≥1 of {num_rolls} attempts succeed",
        format_pct(p_at_least_one),
        help="At least one roll attempt hits your threshold. "
        "Useful for powers that let you keep rolling until you succeed once.",
    )
    m5.metric(
        f"All {num_rolls} attempts succeed",
        format_pct(p_all_success),
        help="Every roll attempt hits your threshold. "
        "Useful for powers that reward success on each roll.",
    )
    m6.metric(
        f"All {num_rolls} attempts fail",
        format_pct(p_all_fail),
        help="None of your roll attempts hit your threshold.",
    )

    with st.expander("What do these probabilities mean?", expanded=True):
        st.markdown(
            f"""
**Single die matches ({format_pct(p_die)})**  
One die is rolled. This is the chance its face is a required food type.
Invertebrate and seed each match 2 of 6 faces because of the wild face.

**One attempt succeeds ({format_pct(p_per_roll)})**  
You roll **{dice_per_roll}** dice once. The attempt succeeds if **≥{min_matches}**
show the required food. Hunting powers like “if any are rodent” use
**{min_matches}** match with **1** attempt.

**One attempt fails ({format_pct(1 - p_per_roll)})**  
The complement of a single attempt succeeding.

**≥1 of {num_rolls} attempts succeed ({format_pct(p_at_least_one)})**  
You get **{num_rolls}** independent tries. This is the chance **at least one**
attempt succeeds — even if others fail. Example: roll up to 3 times and stop
when you hit once.

**All {num_rolls} attempts succeed ({format_pct(p_all_success)})**  
Every attempt must succeed. Example: a power that caches food on **each**
successful roll across **{num_rolls}** tries.

**All {num_rolls} attempts fail ({format_pct(p_all_fail)})**  
No attempt meets the threshold.
"""
        )

    st.caption(
        f"Selected foods ({', '.join(selected_foods)}) match "
        f"{int(p_die * len(DIE_FACE_OPTIONS))} of {len(DIE_FACE_OPTIONS)} faces on each die."
    )

    st.subheader("Matching dice on one roll")
    st.caption(
        "Distribution for a single attempt: how many of the rolled dice show the required food."
    )
    st.altair_chart(
        build_dice_match_chart(int(dice_per_roll), p_die),
        use_container_width=True,
    )


def render_draw_tab(birds: pd.DataFrame, all_expansions: list[str]) -> None:
    with st.sidebar:
        st.header("Expansions")
        selected_expansions = []
        for expansion in all_expansions:
            label = EXPANSION_LABELS.get(expansion, expansion.title())
            default_on = True
            if st.checkbox(label, value=default_on, key=f"exp_{expansion}"):
                selected_expansions.append(expansion)

        st.divider()
        st.header("Card attributes")

        vp_min, vp_max = st.slider(
            "Victory points",
            min_value=0,
            max_value=int(birds["Victory points"].max()),
            value=(0, int(birds["Victory points"].max())),
        )
        food_min, food_max = st.slider(
            "Total food cost",
            min_value=0,
            max_value=int(birds["Total food cost"].max()),
            value=(0, int(birds["Total food cost"].max())),
        )

        numeric_wingspans = pd.to_numeric(birds["Wingspan"], errors="coerce")
        ws_min_bound = int(numeric_wingspans.min())
        ws_max_bound = int(numeric_wingspans.max())
        wingspan_min, wingspan_max = st.slider(
            "Wingspan (cm)",
            min_value=ws_min_bound,
            max_value=ws_max_bound,
            value=(ws_min_bound, ws_max_bound),
        )
        unlisted_wingspan = render_tri_state_filter(
            "Unlisted wingspan (*)",
            "unlisted_wingspan",
        )

        power_categories = sorted(
            birds["PowerCategory"].dropna().astype(str).unique().tolist()
        )
        selected_power = st.multiselect(
            "Power category",
            options=power_categories,
            default=[],
        )
        no_power_only = st.checkbox("No power only", value=False)

        nest_types = sorted(birds["Nest type"].dropna().astype(str).unique().tolist())
        selected_nests = st.multiselect("Nest type", options=nest_types, default=[])

        colors = sorted(birds["Color"].dropna().astype(str).unique().tolist())
        selected_colors = st.multiselect("Power color", options=colors, default=[])

        st.subheader("Habitat")
        selected_habitats = st.multiselect(
            "Has habitat",
            options=HABITAT_COLUMNS,
            default=[],
        )
        habitat_mode = st.radio(
            "Habitat match mode",
            options=["Any selected", "All selected"],
            horizontal=True,
        )

        st.subheader("Traits")
        predator = render_tri_state_filter("Predator", "predator")
        flocking = render_tri_state_filter("Flocking", "flocking")
        bonus_card = render_tri_state_filter("Bonus card icon", "bonus_card")

        st.subheader("Food requirements")
        selected_food = st.multiselect(
            "Requires food type",
            options=FOOD_COLUMNS,
            default=[],
        )
        requires_wild = st.checkbox("Requires wild food token", value=False)
        alternate_cost = render_tri_state_filter("Alternate food cost (/)", "slash_cost")
        wild_cost = render_tri_state_filter("Any-food cost (*)", "star_cost")

        st.subheader("Bonus card tags")
        selected_bonus = st.multiselect(
            "Matches bonus card",
            options=BONUS_CARD_COLUMNS,
            default=[],
        )
        bonus_mode = st.radio(
            "Bonus tag match mode",
            options=["Any selected tag", "All selected tags"],
            horizontal=True,
        )

    if not selected_expansions:
        st.warning("Select at least one expansion in the sidebar.")
        return

    deck = birds[birds["Expansion"].isin(selected_expansions)].copy()
    filtered = deck.copy()

    filtered = filtered[
        filtered["Victory points"].between(vp_min, vp_max, inclusive="both")
    ]
    filtered = filtered[
        filtered["Total food cost"].between(food_min, food_max, inclusive="both")
    ]
    filtered = apply_wingspan_filter(
        filtered,
        wingspan_min,
        wingspan_max,
        unlisted_wingspan,
    )

    if selected_power:
        filtered = filtered[filtered["PowerCategory"].isin(selected_power)]
    if no_power_only:
        filtered = filtered[filtered["PowerCategory"].isna() | (filtered["PowerCategory"] == "")]

    if selected_nests:
        filtered = filtered[filtered["Nest type"].isin(selected_nests)]
    if selected_colors:
        filtered = filtered[filtered["Color"].isin(selected_colors)]

    if selected_habitats:
        mode = "all" if habitat_mode == "All selected" else "any"
        filtered = apply_habitat_filter(filtered, selected_habitats, mode)

    for column, choice in [
        ("Predator", predator),
        ("Flocking", flocking),
        ("Bonus card", bonus_card),
    ]:
        filtered = apply_marker_filter(filtered, column, choice)

    if selected_food or requires_wild:
        food_cols = list(selected_food)
        if requires_wild and "Wild (food)" not in food_cols:
            food_cols.append("Wild (food)")
        filtered = apply_food_filter(filtered, food_cols, min_cost=None)

    filtered = apply_marker_filter(filtered, "/ (food cost)", alternate_cost)
    filtered = apply_marker_filter(filtered, "* (food cost)", wild_cost)

    if selected_bonus:
        if bonus_mode == "All selected tags":
            for column in selected_bonus:
                filtered = apply_marker_filter(filtered, column, "yes")
        else:
            filtered = apply_bonus_filter(filtered, selected_bonus)

    total_cards = len(deck)
    matching_cards = len(filtered)
    single_draw_prob = matching_cards / total_cards if total_cards else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Birds in deck", total_cards)
    col2.metric("Matching birds", matching_cards)
    col3.metric("P(one random draw)", format_pct(single_draw_prob))
    col4.metric(
        "Share of deck",
        format_pct(single_draw_prob),
        help="Same as single-draw probability when drawing uniformly at random.",
    )

    st.subheader("Multi-card draws")
    draw_count = st.slider(
        "Bird cards drawn",
        min_value=1,
        max_value=min(5, total_cards) if total_cards else 1,
        value=2,
        help="Wingspan's draw action usually gives 2 cards from the deck or tray.",
    )

    at_least_one = prob_at_least_one(total_cards, matching_cards, draw_count)
    expected = expected_matches(total_cards, matching_cards, draw_count)

    m1, m2, m3 = st.columns(3)
    m1.metric(f"P(at least 1 match in {draw_count})", format_pct(at_least_one))
    m2.metric(f"P(no matches in {draw_count})", format_pct(1 - at_least_one))
    m3.metric(f"Expected matches in {draw_count}", f"{expected:.2f}")

    st.caption(
        "Multi-card probabilities assume sampling without replacement from the full bird deck."
    )

    left, right = st.columns(2)

    with left:
        st.subheader("Victory points in deck")
        st.caption(
            "Stacked bars show matching vs non-matching birds at each VP. "
            "Labels show counts per segment; percentages are matching share of that VP total."
        )
        st.altair_chart(build_victory_points_chart(deck, filtered), use_container_width=True)

    with right:
        st.subheader("Matching birds by expansion")
        if matching_cards:
            expansion_counts = (
                filtered["Expansion"]
                .map(lambda x: EXPANSION_LABELS.get(x, x))
                .value_counts()
                .rename("Matching birds")
                .to_frame()
                .reset_index()
                .rename(columns={"index": "Expansion"})
            )
            bar = alt.Chart(expansion_counts).mark_bar(color="#6c8ebf").encode(
                x=alt.X(
                    "Expansion:N", 
                    title="Expansion", 
                    axis=alt.Axis(
                        labelFontSize=14, 
                        titleFontSize=16, 
                        labelAngle=-45
                    )
                ),
                y=alt.Y(
                    "Matching birds:Q", 
                    title="Matching birds",
                    axis=alt.Axis(
                        labelFontSize=14, 
                        titleFontSize=16
                    )
                ),
                tooltip=[alt.Tooltip("Expansion:N", title="Expansion"), alt.Tooltip("Matching birds:Q", title="Matching birds")]
            ).properties(height=320)
            st.altair_chart(bar, use_container_width=True)
       
        else:
            st.info("No birds match the current filters.")

    excluded_wingspan = len(deck) - len(deck_with_numeric_wingspan(deck))
    st.subheader("Wingspan in deck")
    st.caption(
        "Stacked bars show matching vs non-matching birds in 25 cm wingspan bins. "
        "Labels show counts per segment; percentages are matching share of that bin. "
        + (
            f"{excluded_wingspan} bird(s) with unlisted wingspan (*) are excluded."
            if excluded_wingspan
            else ""
        )
    )
    st.altair_chart(build_wingspan_chart(deck, filtered), use_container_width=True)

    st.caption(
        "Box plot shows the full wingspan spread for matching vs non-matching birds. "
        "Hover over dots to see individual bird names."
    )
    st.altair_chart(build_wingspan_boxplot(deck, filtered), use_container_width=True)

    st.subheader("Matching birds")
    if matching_cards:
        display_df = filtered[DISPLAY_COLUMNS].sort_values(
            ["Victory points", "Common name"],
            ascending=[False, True],
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("Try relaxing filters or adding more expansions.")

    with st.expander("Full deck breakdown"):
        deck_summary = (
            deck["Expansion"]
            .map(lambda x: EXPANSION_LABELS.get(x, x))
            .value_counts()
            .rename("Birds")
            .to_frame()
        )
        st.dataframe(deck_summary, use_container_width=True)


def main() -> None:
    st.set_page_config(
        page_title="Wingspan Calculator",
        page_icon="🐦",
        layout="wide",
    )
    st.title("Wingspan Calculator")
    st.caption("Draw probabilities and food dice odds for the Wingspan board game.")

    birds = load_birds()
    all_expansions = sorted(birds["Expansion"].unique())

    tab_draw, tab_dice = st.tabs(["Bird draws", "Food dice"])

    with tab_draw:
        render_draw_tab(birds, all_expansions)

    with tab_dice:
        render_dice_tab()


if __name__ == "__main__":
    main()
