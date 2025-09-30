init_locs = [
    dict(
        id=1,
        latitude=59.873972,
        longitude=10.74493,
        name="Malmøya-nord",
        extra_thresh=0.0,
    ),
    dict(
        id=2,
        latitude=59.859773,
        longitude=10.75167,
        name="Malmøya-sør",
        extra_thresh=0.0,
    ),
    dict(
        id=3,
        latitude=59.884846,
        longitude=10.69528,
        name="Nakkholmen-sør",
        extra_thresh=0.0,
    ),
    dict(
        id=4,
        latitude=59.847316,
        longitude=10.57949,
        name="Gåsøya-sør",
        extra_thresh=0.4,
    ),
]
init_locs_values: list[tuple[int, float, float, str, float]] = [
    tuple(loc.values()) for loc in init_locs
]  # type: ignore
