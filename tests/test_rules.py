from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

import pytest

from ats_onebss.models import ProjectRoute, ProjectRule, Ticket
from ats_onebss.models import Member, ServiceRule
from ats_onebss.rules import (
    RuleError,
    canonical_member_name,
    eligible_members,
    load_project_rules,
    load_rules,
    load_score_member_names,
    match_project_rule,
    match_rule,
    member_group,
)
from ats_onebss.config import load_config
from ats_onebss.text import normalize, unaccent


# Shared parsing and routing behavior validated with local synthetic fixtures.

def make_rules(tmp_path):
    path = tmp_path / "rules.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.append([None, None, None, None, "Nhóm 1", None, "Nhóm 2"])
    sheet.append(["STT", "Dịch vụ", "Điểm quy đổi", "Quy tắc", "An", "Bình", "Hoa"])
    sheet.append([1, "Tên miền Việt Nam", 14, "Loại HĐ: Gia hạn, Chấm dứt", "Chính", "Phụ", None])
    sheet.append([2, "Tên miền Việt Nam", 29, "Loại HĐ: Lắp đặt mới, Chuyển quyền", "Chính", None, "Chính"])
    book.save(path)
    return path


def test_loads_separate_google_sheet_service_and_shifted_members(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([None, None, None, None, None, "Nhóm 1"])
    sheet.append([
        "STT", "Dịch vụ", "Dịch vụ trên Google Sheet", "Điểm quy đổi",
        "Quy tắc", "An",
    ])
    sheet.append([1, "ISDN 30B+D cáp đồng", "B-FONE", 17, None, "Chính"])
    path = tmp_path / "rules-new.xlsx"
    workbook.save(path)

    rule = load_rules(path)[0]
    assert rule.service == "ISDN 30B+D cáp đồng"
    assert rule.sheet_service == "B-FONE"
    assert rule.members[0].name == "An"


def test_api_column_is_opt_in_and_not_treated_as_a_member(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([None, None, None, None, "Nhóm 1", None])
    sheet.append(["STT", "Dịch vụ", "Điểm quy đổi", "Quy tắc", "An", "Gửi API"])
    sheet.append([1, "Fiber", 17, "", "Chính", "Có"])
    sheet.append([2, "MetroNet LT", 27, "", "Chính", None])
    path = tmp_path / "rules-api.xlsx"
    workbook.save(path)

    rules = load_rules(path)

    assert rules[0].send_to_api is True
    assert [member.name for member in rules[0].members] == ["An"]
    assert rules[1].send_to_api is False
    assert [member.name for member in rules[1].members] == ["An"]


def test_workbook_without_api_column_preserves_legacy_api_behavior(tmp_path):
    rules = load_rules(make_rules(tmp_path))

    assert all(rule.send_to_api for rule in rules)


def test_policy_text_controls_points_and_google_sheet_output(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([None, None, None, None, "Nhóm 1"])
    sheet.append(["STT", "Dịch vụ", "Điểm quy đổi", "Quy tắc", "An"])
    sheet.append([
        1,
        "Thoại quốc tế",
        99,
        "Không tính điểm, không đưa vào danh sách (Vẫn phân phiếu)",
        "Chính",
    ])
    path = tmp_path / "rules.xlsx"
    workbook.save(path)

    rule = load_rules(path)[0]
    assert rule.points == Decimal("99")
    assert rule.count_points is False
    assert rule.write_to_sheet is False


def test_load_and_match_contract_rule(tmp_path):
    rules = load_rules(make_rules(tmp_path))
    ticket = Ticket("GD1", "TB1", "Dịch vụ CNTT", "Tên miền Việt Nam", "Lắp đặt mới")
    rule = match_rule(rules, ticket)
    assert rule.points == Decimal("29")
    assert rule.row_number == 4


def test_contract_rule_matches_onebss_renewal_wording(tmp_path):
    rules = load_rules(make_rules(tmp_path))
    ticket = Ticket(
        "GD1", "TB1", "Dịch vụ CNTT", "Tên miền Việt Nam",
        "Gia hạn và thay đổi gói cước CNTT/GTGT",
    )
    rule = match_rule(rules, ticket)
    assert rule.points == Decimal("14")


def test_domain_renewal_does_not_fall_back_to_gh_transaction_code(tmp_path):
    rules = load_rules(make_rules(tmp_path))
    ticket = Ticket(
        "CBG-GH/00013381", "domain.vn", "Dịch vụ CNTT", "Tên miền Việt Nam"
    )
    with pytest.raises(RuleError, match="Không tìm thấy quy tắc"):
        match_rule(rules, ticket)


def test_primary_members_are_preferred(tmp_path):
    rules = load_rules(make_rules(tmp_path))
    ticket = Ticket("GD1", "TB1", "Dịch vụ CNTT", "Tên miền Việt Nam", "Gia hạn")
    groups = eligible_members(match_rule(rules, ticket), ticket, use_backups=False)
    assert groups == {"Nhóm 1": ["An"]}


def test_voice_brandname_unknown_vip_is_rejected():
    rule = ServiceRule(
        3, "Voice Brandname", Decimal("20"), "",
        (Member("Lê Đức Tuấn", "Nhóm 2", "Chính"),),
    )
    ticket = Ticket("GD1", "TB1", "Voice Brandname", vip_status="")
    with pytest.raises(RuleError, match="không xác định được VIP xử lý"):
        eligible_members(rule, ticket, False)


def test_canonical_member_name_accepts_unique_vietnamese_tone_typo():
    rules = [
        ServiceRule(
            3, "Fiber", Decimal("17"), "",
            (Member("Đặng Văn Minh", "Nhóm 1", "Chính"),),
        )
    ]
    assert canonical_member_name(rules, "Đăng Văn Minh") == "Đặng Văn Minh"


def test_canonical_member_name_resolves_ly_bich_hang_sheet_alias():
    rules = [
        ServiceRule(
            3, "Fiber", Decimal("17"), "",
            (Member("Lý Thị Bích Hằng", "Nhóm 1", "Chính"),),
        )
    ]

    assert canonical_member_name(rules, "Lý Bích Hằng") == "Lý Thị Bích Hằng"
    assert member_group(rules, "Lý Bích Hằng") == "Nhóm 1"


def test_member_group_uses_service_context_for_employee_in_two_groups():
    group_1 = ServiceRule(
        3, "Fiber", Decimal("17"), "",
        (Member("Lê Đức Tuấn", "Nhóm 1", "Chính"),),
    )
    group_2 = ServiceRule(
        4, "Voice Brandname", Decimal("20"), "",
        (Member("Lê Đức Tuấn", "Nhóm 2", "Chính"),),
    )
    rules = [group_1, group_2]

    assert member_group(rules, "Lê Đức Tuấn", group_1) == "Nhóm 1"
    assert member_group(rules, "Lê Đức Tuấn", group_2) == "Nhóm 2"
    with pytest.raises(RuleError, match="xuất hiện ở nhiều nhóm"):
        member_group(rules, "Lê Đức Tuấn")


def test_loads_and_prioritizes_named_project_rules(tmp_path):
    path = tmp_path / "projects.toml"
    path.write_text(
        '''
[[projects]]
name = "Dự án BCA"
priority = 10
match_fields = ["customer_name", "subscriber_name"]
contains = "Cục Viễn Thông & Cơ Yếu Bca"
route_field = "labor_address"
[[projects.routes]]
assignee = "Đào Anh Vũ"
locations = ["Hà Nội"]

[[projects]]
name = "Đài THVN"
priority = 100
match_fields = ["subscriber_name"]
contains = "Đài THVN"
fixed_assignee = "Nguyễn Hoàng Dương"
''',
        encoding="utf-8",
    )
    rules = load_project_rules(path)
    ticket = Ticket(
        "GD1", "TB1", "Fiber", subscriber_name="Dịch vụ của ĐÀI THVN tại Hà Nội"
    )
    match = match_project_rule(rules, ticket)
    assert match is not None
    assert match.project_name == "Đài THVN"
    assert match.assignee == "Nguyễn Hoàng Dương"


@pytest.mark.parametrize(
    ("address", "assignee"),
    [
        ("Thành phố Hải Phòng", "Vũ Thế Ninh"),
        ("Tỉnh Điện Biên", "Vũ Thế Ninh"),
        ("TP Hà Nội", "Đào Anh Vũ"),
        ("Tỉnh Lai Châu", "Đào Anh Vũ"),
        ("Tỉnh Sơn La", "Đoàn Hải Hà"),
        ("Tỉnh Vĩnh Phúc", "Đoàn Hải Hà"),
        ("Tỉnh Hà Giang", "Nguyễn Duy Thành"),
        ("Tỉnh Thanh Hoá", "Nguyễn Duy Thành"),
        ("Tỉnh Nghệ An", "Nguyễn Duy Thành"),
        ("Tỉnh Hà Tĩnh", "Vũ Thế Ninh"),
    ],
)
def test_bca_routes_by_labor_address(address, assignee):
    rule = ProjectRule(
        name="Dự án BCA",
        contains="Cục Viễn Thông & Cơ Yếu Bca",
        match_fields=("customer_name", "subscriber_name"),
        priority=90,
        route_field="labor_address",
        routes=(
            ProjectRoute("Vũ Thế Ninh", ("Hải Phòng", "Điện Biên", "Hà Tĩnh")),
            ProjectRoute("Đào Anh Vũ", ("Hà Nội", "Lai Châu")),
            ProjectRoute("Đoàn Hải Hà", ("Sơn La", "Vĩnh Phúc")),
            ProjectRoute("Nguyễn Duy Thành", ("Hà Giang", "Thanh Hóa", "Nghệ An")),
        ),
    )
    ticket = Ticket(
        "GD1",
        "TB1",
        "Fiber",
        customer_name="CỤC VIỄN THÔNG & CƠ YẾU BCA",
        labor_address=address,
    )
    match = match_project_rule([rule], ticket)
    assert match is not None
    assert match.project_name == "Dự án BCA"
    assert match.assignee == assignee


def test_bca_unknown_address_is_rejected_instead_of_using_service_rule():
    rule = ProjectRule(
        name="Dự án BCA",
        contains="Cục Viễn Thông & Cơ Yếu Bca",
        match_fields=("customer_name",),
        priority=90,
        route_field="labor_address",
        routes=(ProjectRoute("Đào Anh Vũ", ("Hà Nội",)),),
    )
    ticket = Ticket(
        "GD1", "TB1", "Fiber", customer_name="Cục Viễn Thông & Cơ Yếu Bca"
    )
    with pytest.raises(RuleError, match="Dự án BCA"):
        match_project_rule([rule], ticket)


def test_vietlott_project_routes_tuyen_quang_by_subscriber_prefix(tmp_path):
    path = tmp_path / "projects.toml"
    path.write_text(
        '''
[[projects]]
name = "Dự án Vietlott"
priority = 90
match_fields = ["customer_name"]
contains = "Công Ty Cổ Phần Đầu Tư Kỹ Thuật Berjaya Gia Thịnh"
route_field = "labor_address"

[[projects.routes]]
assignee = "Đào Anh Vũ"
locations = ["Tuyên Quang"]
subscriber_prefixes = ["bgt5"]

[[projects.routes]]
assignee = "Nguyễn Duy Thành"
locations = ["Tuyên Quang"]
subscriber_prefixes = ["bgt2"]
''',
        encoding="utf-8",
    )
    rules = load_project_rules(path)
    base = dict(
        transaction_id="VNP-LD/00078532",
        service="Fiber",
        customer_name="Công Ty Cổ Phần Đầu Tư Kỹ Thuật Berjaya Gia Thịnh",
        labor_address="Thành phố Tuyên Quang",
    )
    assert match_project_rule(
        rules, Ticket(subscriber_id="bgt57174", **base)
    ).assignee == "Đào Anh Vũ"
    assert match_project_rule(
        rules, Ticket(subscriber_id="bgt27174", **base)
    ).assignee == "Nguyễn Duy Thành"
