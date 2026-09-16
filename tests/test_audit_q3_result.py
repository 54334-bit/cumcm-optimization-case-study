"""审计脚本的可移植路径接口测试。"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from audit_q3_result import build_parser


def test_parser_requires_explicit_input_paths() -> None:
    """脚本只能从调用者显式给出的路径读取输入，不能内置个人绝对路径。"""
    parser = build_parser()
    args = parser.parse_args(
        [
            "--result-workbook", "data/local/result3_v2.xlsx",
            "--price-workbook", "data/local/attachment1.xlsx",
            "--output", "results/tables/q3_fee_audit.txt",
        ]
    )

    assert args.result_workbook == Path("data/local/result3_v2.xlsx")
    assert args.price_workbook == Path("data/local/attachment1.xlsx")
    assert args.output == Path("results/tables/q3_fee_audit.txt")
