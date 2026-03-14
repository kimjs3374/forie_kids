from datetime import datetime

from flask import redirect, request, url_for


def _redirect_back(default_endpoint="admin.dashboard"):
    next_url = request.form.get("next") or request.args.get("next")
    if next_url:
        return redirect(next_url)
    return redirect(url_for(default_endpoint))


def _build_month_year_choices(months=None):
    current_year = datetime.now().year
    year_candidates = {current_year, current_year + 1}

    for month in months or []:
        target_month = month.get("target_month", "")
        try:
            year_candidates.add(int(str(target_month).split("-")[0]))
        except (TypeError, ValueError, IndexError):
            continue

    sorted_years = sorted(year_candidates)
    year_choices = [(year, f"{year}년") for year in sorted_years]
    month_choices = [(month, f"{month}월") for month in range(1, 13)]
    return year_choices, month_choices
