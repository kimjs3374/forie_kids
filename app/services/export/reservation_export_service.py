from io import BytesIO

from openpyxl import Workbook


def build_reservations_workbook(reservations):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "reservations"
    sheet.append(
        [
            "예약월",
            "이름",
            "동",
            "호수",
            "연락처",
            "아이수",
            "상태",
            "신청일시",
        ]
    )

    for reservation in reservations:
        month = reservation.get("month", {})
        sheet.append(
            [
                month.get("target_month", ""),
                reservation.get("name", ""),
                reservation.get("apt_dong", ""),
                reservation.get("apt_ho", ""),
                reservation.get("phone", ""),
                reservation.get("children_count", ""),
                reservation.get("status_label", reservation.get("status", "")),
                str(reservation.get("created_at", ""))[:16].replace("T", " "),
            ]
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
