import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
import pandas as pd

# 1. Googleスプレッドシートとの連携設定
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_gspread_client():
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
    return gspread.authorize(creds)

sheet = None
try:
    gc = get_gspread_client()
    spreadsheet = gc.open("我が家の家計簿データ")
    sheet = spreadsheet.get_worksheet(0)
    st.sidebar.success("スプレッドシート接続成功！")
except Exception as e:
    st.sidebar.error(f"接続エラー: {e}")

# 2. アプリ画面の作成
st.title("我が家の家計簿アプリ")

# --- サイドバー：設定（子どもの名前の変更など） ---
st.sidebar.header("⚙️ アプリ設定")
st.sidebar.subheader("👨‍👩‍👧‍👦 子どもの名前設定")
child1_name = st.sidebar.text_input("子ども1の名前", "子ども1")
child2_name = st.sidebar.text_input("子ども2の名前", "子ども2")
child3_name = st.sidebar.text_input("子ども3の名前", "子ども3")

# --- データの読み込みと集計用DataFrameの準備 ---
df = pd.DataFrame()
if sheet is not None:
    try:
        raw_data = sheet.get_all_records()
        if raw_data:
            df = pd.DataFrame(raw_data)
            
            # 列名が日本語の場合でも英語に統一して処理できるようにする
            rename_map = {
                '日付': 'Date', 'Date': 'Date',
                '区分': 'Type', 'Type': 'Type',
                '対象者': 'Target', 'Target': 'Target',
                'カテゴリ': 'Category', 'Category': 'Category',
                '金額': 'Amount', 'Amount': 'Amount',
                'メモ': 'Memo', 'Memo': 'Memo'
            }
            df = df.rename(columns=rename_map)
            
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df['Year'] = df['Date'].dt.year
                df['Month'] = df['Date'].dt.month
                df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
    except Exception as e:
        st.warning(f"データ読み込みエラー: {e}")

# --- 📊 収支ダッシュボード（一目でわかるサマリー＆グラフ） ---
if not df.empty and 'Type' in df.columns and 'Amount' in df.columns:
    st.header("📊 収支ダッシュボード")
    
    tab_month, tab_year = st.tabs(["📅 月別サマリー", "📈 年間サマリー"])
    
    with tab_month:
        df['YearMonth'] = df['Date'].dt.strftime('%Y年%m月')
        available_months = sorted([m for m in df['YearMonth'].dropna().unique()], reverse=True)
        
        if available_months:
            selected_month = st.selectbox("表示する月を選択", available_months)
            monthly_df = df[df['YearMonth'] == selected_month]
            
            total_income = monthly_df[monthly_df['Type'] == '収入']['Amount'].sum()
            total_expense = monthly_df[monthly_df['Type'] == '支出']['Amount'].sum()
            balance = total_income - total_expense
            
            col1, col2, col3 = st.columns(3)
            col1.metric("総収入", f"{total_income:,.0f} 円")
            col2.metric("総支出", f"{total_expense:,.0f} 円")
            
            balance_label = "黒字 🟢" if balance >= 0 else "赤字 🔴"
            col3.metric("収支バランス", f"{balance:,.0f} 円", delta=balance_label, delta_color="normal" if balance >= 0 else "inverse")
            
            # カテゴリ別の支出集計とグラフ表示
            st.subheader("🏷️ 今月のカテゴリ別支出（内訳とグラフ）")
            expense_df = monthly_df[monthly_df['Type'] == '支出']
            if not expense_df.empty:
                cat_expense = expense_df.groupby('Category')['Amount'].sum().reset_index()
                cat_expense = cat_expense.sort_values(by='Amount', ascending=False)
                
                chart_data = cat_expense.set_index('Category')['Amount']
                st.bar_chart(chart_data)
                
                st.dataframe(
                    cat_expense.rename(columns={'Category': 'カテゴリ', 'Amount': '合計金額 (円)'}),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("今月の支出データはまだありません。")
        else:
            st.info("有効な日付データがありません。")
            
    with tab_year:
        available_years = sorted([y for y in df['Year'].dropna().unique()], reverse=True)
        if available_years:
            selected_year = st.selectbox("表示する年を選択", available_years)
            yearly_df = df[df['Year'] == selected_year]
            
            y_income = yearly_df[yearly_df['Type'] == '収入']['Amount'].sum()
            y_expense = yearly_df[yearly_df['Type'] == '支出']['Amount'].sum()
            y_balance = y_income - y_expense
            
            y_col1, y_col2, y_col3 = st.columns(3)
            y_col1.metric("年間総収入", f"{y_income:,.0f} 円")
            y_col2.metric("年間総支出", f"{y_expense:,.0f} 円")
            y_balance_label = "黒字 🟢" if y_balance >= 0 else "赤字 🔴"
            y_col3.metric("年間収支", f"{y_balance:,.0f} 円", delta=y_balance_label, delta_color="normal" if y_balance >= 0 else "inverse")
        else:
            st.info("有効な年データがありません。")

st.divider()

# --- 📝 データの入力エリア ---
st.header("📝 収支の入力")

with st.form("kakeibo_form", clear_on_submit=True):
    input_date = st.date_input("日付", date.today())
    input_type = st.radio("区分", ["支出", "収入"], horizontal=True)
    
    # 対象者（デフォルトを「家族共通」に指定: index=2）
    targets = ["パパ", "ママ", "家族共通", child1_name, child2_name, child3_name]
    input_target = st.selectbox("対象者", targets, index=2)
    
    # カテゴリ
    categories = [
        "食費", "固定費", "保険代", "NISA・投資", "日用品", 
        "個人出費", "給料", "その他収入", "その他支出"
    ]
    input_category = st.selectbox("カテゴリ", categories)
    
    input_amount = st.number_input("金額 (円)", min_value=0, step=100)
    
    # --- メモ（選択式 ＋ 自由記入） ---
    st.write("メモ（よく使う項目から選択、または直接入力）")
    memo_choices = [
        "選択なし", 
        "外食", 
        "ネット", 
        "携帯", 
        "水道", 
        "ガス", 
        "電気", 
        "家のローン", 
        "自由に入力する"
    ]
    selected_memo_option = st.selectbox("よく使う項目", memo_choices, label_visibility="collapsed")
    
    if selected_memo_option == "自由に入力する":
        input_memo = st.text_input("自由メモを入力してください")
    elif selected_memo_option != "選択なし":
        input_memo = selected_memo_option
    else:
        input_memo = ""
    
    submit_button = st.form_submit_button("データを保存する")

# --- 保存処理 ---
if submit_button:
    if input_amount <= 0:
        st.warning("金額を入力してください。")
    elif sheet is None:
        st.error("スプレッドシートと接続できていないため保存できません。")
    else:
        try:
            row = [
                str(input_date),
                input_type,
                input_target,
                input_category,
                input_amount,
                input_memo
            ]
            sheet.append_row(row)
            st.success(f"保存しました！: {input_target} / {input_category} / {input_amount:,}円")
            st.rerun()
        except Exception as e:
            st.error(f"保存失敗: {e}")

# --- 📊 過去の履歴確認 ---
st.divider()
st.header("📊 最近の入力履歴")

if sheet is not None:
    try:
        data = sheet.get_all_records()
        if data:
            st.dataframe(data[::-1], use_container_width=True)
        else:
            st.info("まだデータがありません。")
    except Exception as e:
        st.write(f"履歴取得エラー: {e}")
else:
    st.info("スプレッドシートが接続されると履歴が表示されます。")
    