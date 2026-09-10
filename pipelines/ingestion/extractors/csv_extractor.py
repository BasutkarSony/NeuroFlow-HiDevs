import io

import pandas as pd

from . import ExtractedPage


def extract_csv(file_bytes: bytes) -> list[ExtractedPage]:
    df = pd.read_csv(io.BytesIO(file_bytes))
    pages: list[ExtractedPage] = []

    if len(df) < 1000:
        for start in range(0, len(df), 100):
            block = df.iloc[start:start + 100]

            content = block.to_markdown(
                index=False
            )

            pages.append(
                ExtractedPage(
                    page_number=(start // 100) + 1,
                    content=content,
                    content_type="table",
                    metadata={
                        "rows": len(block),
                        "start_row": start,
                        "end_row": start + len(block),
                        "total_rows": len(df),
                    },
                )
            )

        return pages

    summary_lines = [
        f"Rows: {len(df)}",
        f"Columns: {len(df.columns)}",
        "",
        "Column Summary:",
    ]

    for column in df.columns:
        series = df[column]

        if pd.api.types.is_numeric_dtype(series):
            summary_lines.append(
                f"- {column}: dtype={series.dtype}, "
                f"min={series.min()}, "
                f"max={series.max()}, "
                f"mean={series.mean()}"
            )
        else:
            top_values = (
                series.astype(str)
                .value_counts()
                .head(5)
                .to_dict()
            )

            summary_lines.append(
                f"- {column}: dtype={series.dtype}, "
                f"top-5={top_values}"
            )

    summary_lines.extend(
        [
            "",
            "Sample Rows:",
            df.head(10).to_markdown(index=False),
        ]
    )

    summary = "\n".join(summary_lines)

    pages.append(
        ExtractedPage(
            page_number=1,
            content=summary,
            content_type="table",
            metadata={
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "large_csv": True,
            },
        )
    )

    return pages