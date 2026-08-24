from __future__ import annotations

import tempfile
import hmac
from pathlib import Path

import streamlit as st

from excel_writer import build_excel
from pdf_parser import parse_pdfs
from validator import collect_warnings, validate_generated

APP_DIR = Path(__file__).resolve().parent
BUNDLED_TEMPLATE = APP_DIR / "reference" / "template.xlsx"

st.set_page_config(page_title="室内土質試験結果 Excel変換", page_icon="📊", layout="wide")

def require_password() -> None:
    """Streamlit Secrets の APP_PASSWORD でアプリを保護する。"""
    try:
        expected = str(st.secrets["APP_PASSWORD"])
    except Exception:
        st.error("管理者設定エラー：StreamlitのSecretsに APP_PASSWORD が設定されていません。")
        st.info('App settings → Secrets に  APP_PASSWORD = "任意のパスワード"  を設定してください。')
        st.stop()

    if st.session_state.get("authenticated", False):
        with st.sidebar:
            st.success("認証済み")
            if st.button("ログアウト"):
                st.session_state["authenticated"] = False
                st.rerun()
        return

    st.title("🔒 室内土質試験結果 PDF → Excel")
    st.caption("このアプリはパスワードで保護されています。")

    with st.form("login_form", clear_on_submit=False):
        entered = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン", type="primary")

    if submitted:
        if hmac.compare_digest(entered, expected):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")

    st.stop()

require_password()
st.title("室内土質試験結果 PDF → Excel")
st.caption("JGS『土質試験結果一覧表（基礎地盤）』のPDFを、試料数に合わせた一覧表へ変換します。")

with st.expander("変換ルール", expanded=False):
    st.markdown(
        """
- PDFの数値は四捨五入・補正・推測をしません。
- 孔番は **No.の数字が若い順** に並べます。
- 各No.の前に項目・単位を付け、No.間は **完全な空白行を1行** 入れます。
- 地層記号はNo.ごとに1つの空欄結合セルにします。
- シルト分・粘土分が個別記載なら別セル、まとめ記載ならそのデータ行だけ2セルを結合します。
- **Fcのみ**、個別記載時はシルト分＋粘土分で計算します。
"""
    )

pdfs = st.file_uploader(
    "室内土質試験結果PDFを選択（複数可）",
    type=["pdf"],
    accept_multiple_files=True,
)

template_upload = st.file_uploader(
    "Excelテンプレート（任意）",
    type=["xlsx"],
    help="未選択の場合は、完成版を基準にした内蔵テンプレートを使用します。",
)

if st.button("解析してExcelを作成", type="primary", disabled=not pdfs):
    with st.spinner("PDFを解析しています…"):
        holes = parse_pdfs([f.getvalue() for f in pdfs])

    if not holes:
        st.error("対応する『土質試験結果一覧表（基礎地盤）』を検出できませんでした。")
        st.stop()

    st.subheader("検出結果")
    cols = st.columns(min(len(holes), 4))
    for i, hole in enumerate(holes):
        with cols[i % len(cols)]:
            st.metric(f"No.{hole.hole_no}", f"{len(hole.samples)} 試料")

    warnings = collect_warnings(holes)
    if warnings:
        st.warning(f"要確認：{len(warnings)}件")
        with st.expander("要確認内容"):
            for w in warnings:
                st.write("-", w)

    with tempfile.TemporaryDirectory() as td:
        if template_upload is not None:
            template_path = Path(td) / "template.xlsx"
            template_path.write_bytes(template_upload.getvalue())
        else:
            template_path = BUNDLED_TEMPLATE

        try:
            xlsx_bytes, meta = build_excel(holes, template_path)
        except Exception as exc:
            st.exception(exc)
            st.stop()

    mismatches = validate_generated(xlsx_bytes, holes, meta["row_map"])
    if mismatches:
        st.error(f"PDF抽出値とExcel書込値の不一致：{len(mismatches)}件")
        st.dataframe(mismatches, use_container_width=True)
    else:
        st.success("PDF抽出値とExcel書込値の照合：不一致 0件")

    hole_text = "_".join(str(h.hole_no) for h in holes)
    st.download_button(
        "完成Excelをダウンロード",
        data=xlsx_bytes,
        file_name=f"室内土質試験結果_No{hole_text}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
