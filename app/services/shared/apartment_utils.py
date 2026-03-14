def build_apt_unit(apt_dong, apt_ho):
    return f"{str(apt_dong or '').strip()}동 {str(apt_ho or '').strip()}호"


def split_apt_unit(apt_unit):
    value = apt_unit or ""
    if "동" in value and "호" in value:
        try:
            dong, rest = value.split("동", 1)
            ho = rest.replace("호", "").strip()
            return dong.strip(), ho
        except ValueError:
            return value, ""
    return value, ""
