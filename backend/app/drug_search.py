
import sqlite3
import streamlit as st
from st_keyup import st_keyup


# =========================================================
# CONFIG
# =========================================================

DB_PATH = "data/darooyab.db"


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="سیستم ثبت دارو",
    page_icon="💊",
    layout="centered",
)


# =========================================================
# DATABASE
# =========================================================

@st.cache_resource
def get_connection():
    return sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )


def search_drugs(query, limit=20):

    query = query.strip()

    if not query:
        return []

    conn = get_connection()

    pattern = f"%{query}%"
    starts_with = f"{query}%"

    # تشخیص زبان جستجو
    is_english = any(
        "a" <= char.lower() <= "z"
        for char in query
    )

    if is_english:

        order_sql = """
            CASE
                WHEN brand_name_en LIKE ? THEN 0
                WHEN generic_name_en LIKE ? THEN 1
                WHEN brand_name_fa LIKE ? THEN 2
                ELSE 3
            END,
            brand_name_en
        """

    else:

        order_sql = """
            CASE
                WHEN brand_name_fa LIKE ? THEN 0
                WHEN brand_name_en LIKE ? THEN 1
                WHEN generic_name_en LIKE ? THEN 2
                ELSE 3
            END,
            brand_name_fa
        """

    sql = f"""
        SELECT
            id,
            brand_name_fa,
            brand_name_en,
            generic_name_en,
            form,
            strength,
            manufacturer
        FROM drugs
        WHERE
            brand_name_fa LIKE ?
            OR brand_name_en LIKE ?
            OR generic_name_en LIKE ?
        ORDER BY
            {order_sql}
        LIMIT ?
    """

    params = (
        pattern,
        pattern,
        pattern,
        starts_with,
        starts_with,
        starts_with,
        limit,
    )

    return conn.execute(
        sql,
        params
    ).fetchall()


# =========================================================
# DOSE UNIT ENGINE
# =========================================================

def get_dose_unit(
    form,
    brand_name_en="",
    generic_name_en="",
    brand_name_fa="",
    strength=""
):
    """
    تعیین خودکار واحد مصرف دارو.

    اولویت تشخیص:

    1. موارد خاص مثل Insulin
    2. Nebulization
    3. Inhaler / MDI / Puff
    4. فرم‌های مایع
    5. فرم‌های موضعی
    6. فرم ثبت‌شده در دیتابیس
    7. در نهایت fallback = واحد

    دلیل:
    بعضی رکوردهای دیتابیس form خالی دارند و فرم
    دارو فقط در brand_name_en یا brand_name_fa مشخص است.
    """

    # ---------------------------------------------------------
    # Normalize text
    # ---------------------------------------------------------

    form = (
        form or ""
    ).upper().strip()

    brand_en = (
        brand_name_en or ""
    ).upper().strip()

    generic_en = (
        generic_name_en or ""
    ).upper().strip()

    brand_fa = (
        brand_name_fa or ""
    ).strip()

    strength_text = (
        strength or ""
    ).upper().strip()

    searchable_text_en = (
        f"{brand_en} {generic_en}"
    )

    searchable_text_fa = brand_fa

    searchable_all_en = (
        f"{searchable_text_en} {strength_text}"
    )


    # =========================================================
    # 1. INSULIN
    # =========================================================

    if (
        "INSULIN" in searchable_text_en
        or "انسولین" in searchable_text_fa
    ):
        return "واحد (Unit)"


    # =========================================================
    # 2. NEBULIZATION
    # =========================================================
    #
    # مثال:
    # SALBUTAMOL GHAZI 2.5 mg/2.5 ml Nebulization
    #
    # در این حالت form دیتابیس خالی است، اما عبارت
    # Nebulization در نام انگلیسی وجود دارد.
    #
    # واحد = میلی‌لیتر
    # =========================================================

    if (
        "NEBULIZATION" in searchable_all_en
        or "NEBULIZER" in searchable_all_en
        or "NEBULI" in searchable_all_en
        or "NEBULE" in searchable_all_en
        or "نبولایز" in searchable_text_fa
        or "نبولایزر" in searchable_text_fa
        or "نبول" in searchable_text_fa
    ):
        return "میلی‌لیتر"


    # =========================================================
    # 3. INHALER / MDI / PUFF
    # =========================================================
    #
    # مثال:
    # Salbutamol Inhaler
    # Salbutamol MDI
    #
    # واحد = پاف
    # =========================================================

    if (
        "INHALER" in searchable_all_en
        or "MDI" in searchable_all_en
        or "METERED DOSE" in searchable_all_en
        or "PUFF" in searchable_all_en
        or "INHALATION AEROSOL" in searchable_all_en
        or "اسپری" in searchable_text_fa
        or "اینهالر" in searchable_text_fa
        or "استنشاقی" in searchable_text_fa
    ):
        return "پاف"


    # =========================================================
    # 4. SUSPENSION
    # =========================================================

    if (
        form == "SUSPENSION"
        or "SUSP" in searchable_all_en
        or "SUSPENSION" in searchable_all_en
        or "سوسپانسیون" in searchable_text_fa
    ):
        return "میلی‌لیتر"


    # =========================================================
    # 5. SYRUP
    # =========================================================

    if (
        form == "SYRUP"
        or "SYRUP" in searchable_all_en
        or "شربت" in searchable_text_fa
    ):
        return "میلی‌لیتر"


    # =========================================================
    # 6. SOLUTION
    # =========================================================

    if (
        form == "SOLUTION"
        or "SOLUTION" in searchable_all_en
        or "محلول" in searchable_text_fa
    ):
        return "میلی‌لیتر"


    # =========================================================
    # 7. ORAL DROPS
    # =========================================================

    if (
        form == "DROP"
        or "DROP" in searchable_all_en
        or "DROPS" in searchable_all_en
        or "قطره" in searchable_text_fa
    ):
        return "قطره"


    # =========================================================
    # 8. TOPICAL LIQUID / LOTION
    # =========================================================

    if (
        form == "LOTION"
        or "LOTION" in searchable_all_en
        or "لوسیون" in searchable_text_fa
    ):
        return "میلی‌لیتر"


    # =========================================================
    # 9. CREAM / GEL / OINTMENT
    # =========================================================

    if (
        form in ["CREAM", "GEL", "OINT"]
        or "CREAM" in searchable_all_en
        or "GEL" in searchable_all_en
        or "OINTMENT" in searchable_all_en
        or "پماد" in searchable_text_fa
        or "کرم" in searchable_text_fa
        or "ژل" in searchable_text_fa
    ):
        return "گرم"


    # =========================================================
    # 10. SPRAY
    # =========================================================

    if form == "SPRAY":

        # اگر قبلاً Inhaler/MDI تشخیص داده نشده،
        # به‌صورت عمومی پاف در نظر می‌گیریم.
        return "پاف"


    # =========================================================
    # 11. STANDARD DATABASE FORMS
    # =========================================================

    mapping = {

        # -----------------------------------------------------
        # Oral solid
        # -----------------------------------------------------

        "TAB": "قرص",

        "EFF": "قرص جوشان",

        "CAP": "کپسول",

        "SOFTGEL": "سافت‌ژل",

        "SACHET": "ساشه",


        # -----------------------------------------------------
        # Oral liquid
        # -----------------------------------------------------

        "SYRUP": "میلی‌لیتر",

        "SOLUTION": "میلی‌لیتر",

        "SUSPENSION": "میلی‌لیتر",


        # -----------------------------------------------------
        # Drops
        # -----------------------------------------------------

        "DROP": "قطره",


        # -----------------------------------------------------
        # Injectable
        # -----------------------------------------------------

        "AMP": "آمپول",

        "VIAL": "ویال",

        "INJ": "واحد (Unit)",


        # -----------------------------------------------------
        # Topical
        # -----------------------------------------------------

        "CREAM": "گرم",

        "GEL": "گرم",

        "OINT": "گرم",

        "LOTION": "میلی‌لیتر",


        # -----------------------------------------------------
        # Respiratory
        # -----------------------------------------------------

        "SPRAY": "پاف",


        # -----------------------------------------------------
        # Rectal
        # -----------------------------------------------------

        "SUPP": "شیاف",


        # -----------------------------------------------------
        # Transdermal
        # -----------------------------------------------------

        "PATCH": "پچ",


        # -----------------------------------------------------
        # Shampoo
        # -----------------------------------------------------

        "SHAMPOO": "میلی‌لیتر",


        # -----------------------------------------------------
        # Powder
        # -----------------------------------------------------

        "POWDER": "واحد",
    }


    # =========================================================
    # 12. FORM MAPPING
    # =========================================================

    if form in mapping:

        return mapping[form]


    # =========================================================
    # 13. FALLBACK
    # =========================================================

    return "واحد"


# =========================================================
# DRUG OBJECT
# =========================================================

def make_drug_dict(drug):

    return {

        "id":
            drug[0],

        "brand_name_fa":
            drug[1],

        "brand_name_en":
            drug[2],

        "generic_name_en":
            drug[3],

        "form":
            drug[4],

        "strength":
            drug[5],

        "manufacturer":
            drug[6],
    }


# =========================================================
# SESSION STATE
# =========================================================

if "selected_drugs" not in st.session_state:

    st.session_state.selected_drugs = []


if "dose_values" not in st.session_state:

    st.session_state.dose_values = {}


# =========================================================
# HEADER
# =========================================================

st.title(
    "💊 سیستم ثبت دارو"
)

st.caption(
    "داروهایی را که در حال حاضر مصرف می‌کنید "
    "جستجو و انتخاب کنید."
)


# =========================================================
# STEP 1 — SEARCH
# =========================================================

st.subheader(
    "۱. انتخاب دارو"
)


query = st_keyup(

    "نام دارو را وارد کنید",

    placeholder=(
        "مثلاً گلوکوفاژ، متفورمین، amoxicillin..."
    ),

    key="drug_search",

    debounce=100,
)


# =========================================================
# SEARCH RESULTS
# =========================================================

if query and query.strip():

    results = search_drugs(query)

    st.caption(
        f"{len(results)} نتیجه"
    )

    if not results:

        st.info(
            "دارویی با این عبارت پیدا نشد."
        )

    else:

        # تشخیص زبان جستجو

        is_english = any(
            "a" <= char.lower() <= "z"
            for char in query
        )


        for drug in results:

            (
                drug_id,
                brand_fa,
                brand_en,
                generic,
                form,
                strength,
                manufacturer,
            ) = drug


            # -------------------------------------------------
            # نمایش نتیجه
            # -------------------------------------------------

            if is_english:

                label = (
                    brand_en
                    or brand_fa
                )

            else:

                label = (
                    brand_fa
                    or brand_en
                )


            # -------------------------------------------------
            # جلوگیری از انتخاب دوباره
            # -------------------------------------------------

            already_selected = any(

                isinstance(item, dict)

                and item.get("id") == drug_id

                for item in
                st.session_state.selected_drugs
            )


            # -------------------------------------------------
            # Already selected
            # -------------------------------------------------

            if already_selected:

                st.button(

                    f"✓ {label} — قبلاً انتخاب شده",

                    key=f"selected_{drug_id}",

                    disabled=True,

                    use_container_width=True,
                )


            # -------------------------------------------------
            # New drug
            # -------------------------------------------------

            else:

                if st.button(

                    label,

                    key=f"drug_{drug_id}",

                    use_container_width=True,
                ):

                    selected_drug = make_drug_dict(
                        drug
                    )

                    st.session_state.selected_drugs.append(
                        selected_drug
                    )

                    st.rerun()


# =========================================================
# SELECTED DRUGS
# =========================================================

if st.session_state.selected_drugs:

    st.divider()

    st.subheader(

        f"۲. داروهای انتخاب‌شده "
        f"({len(st.session_state.selected_drugs)})"
    )


    # =====================================================
    # DRUG CARDS
    # =====================================================

    for index, drug in enumerate(

        st.session_state.selected_drugs

    ):

        drug_id = drug["id"]


        brand_fa = drug.get(
            "brand_name_fa",
            ""
        )


        brand_en = drug.get(
            "brand_name_en",
            ""
        )


        generic = drug.get(
            "generic_name_en",
            ""
        )


        form = drug.get(
            "form",
            ""
        )


        strength = drug.get(
            "strength",
            ""
        )


        manufacturer = drug.get(
            "manufacturer",
            ""
        )


        # -------------------------------------------------
        # تعیین واحد مصرف به صورت خودکار
        # -------------------------------------------------

        dose_unit = get_dose_unit(

            form=form,

            brand_name_en=brand_en,

            generic_name_en=generic,

            brand_name_fa=brand_fa,

            strength=strength,
        )


        # =================================================
        # CARD
        # =================================================

        with st.container(border=True):


            # -------------------------------------------------
            # Header
            # -------------------------------------------------

            col1, col2 = st.columns(
                [5, 1]
            )


            with col1:

                st.markdown(

                    f"### {index + 1}. "
                    f"{brand_fa or brand_en}"
                )


                if brand_en:

                    st.caption(
                        brand_en
                    )


            with col2:

                if st.button(

                    "🗑️",

                    key=f"remove_{drug_id}",
                ):

                    st.session_state.selected_drugs.pop(
                        index
                    )


                    st.session_state.dose_values.pop(
                        drug_id,
                        None
                    )


                    st.rerun()


            # -------------------------------------------------
            # اطلاعات دارو
            # -------------------------------------------------

            col1, col2 = st.columns(2)


            with col1:

                st.write(

                    f"**Generic:** "
                    f"{generic or '-'}"
                )


                st.write(

                    f"**Strength:** "
                    f"{strength or '-'}"
                )


            with col2:

                st.write(

                    f"**Form:** "
                    f"{form or '-'}"
                )


                st.write(

                    f"**Manufacturer:** "
                    f"{manufacturer or '-'}"
                )


            st.markdown("---")


            # =================================================
            # CURRENT MEDICATION USAGE
            # =================================================

            st.markdown(
                "**نحوه مصرف فعلی**"
            )


            # -------------------------------------------------
            # مقدار مصرف
            # -------------------------------------------------

            dose_amount = st.number_input(

                f"مقدار مصرف در هر نوبت "
                f"({dose_unit})",

                min_value=0.1,

                step=0.5,

                value=1.0,

                key=f"dose_amount_{drug_id}",
            )


            # -------------------------------------------------
            # نوع برنامه مصرف
            # -------------------------------------------------

            frequency_type_label = st.radio(

                "برنامه مصرف",

                [
                    "روزانه",
                    "هفتگی",
                    "هر چند ساعت",
                ],

                horizontal=True,

                key=f"frequency_type_{drug_id}",
            )


            # =================================================
            # DAILY
            # =================================================

            if frequency_type_label == "روزانه":

                frequency_per_day = st.number_input(

                    "تعداد دفعات مصرف در روز",

                    min_value=1,

                    max_value=24,

                    value=1,

                    step=1,

                    key=f"frequency_day_{drug_id}",
                )


                st.session_state.dose_values[
                    drug_id
                ] = {

                    "amount":
                        dose_amount,

                    "unit":
                        dose_unit,

                    "frequency_type":
                        "daily",

                    "frequency_per_day":
                        frequency_per_day,

                    "frequency_per_week":
                        None,

                    "interval_hours":
                        None,
                }


                st.info(

                    f"💊 "
                    f"{dose_amount:g} "
                    f"{dose_unit} "
                    f"در هر نوبت، "
                    f"{frequency_per_day} "
                    f"بار در روز"
                )


            # =================================================
            # WEEKLY
            # =================================================

            elif frequency_type_label == "هفتگی":

                frequency_per_week = st.number_input(

                    "تعداد دفعات مصرف در هفته",

                    min_value=1,

                    max_value=7,

                    value=5,

                    step=1,

                    key=f"frequency_week_{drug_id}",
                )


                st.session_state.dose_values[
                    drug_id
                ] = {

                    "amount":
                        dose_amount,

                    "unit":
                        dose_unit,

                    "frequency_type":
                        "weekly",

                    "frequency_per_day":
                        None,

                    "frequency_per_week":
                        frequency_per_week,

                    "interval_hours":
                        None,
                }


                st.info(

                    f"💊 "
                    f"{dose_amount:g} "
                    f"{dose_unit} "
                    f"{frequency_per_week} "
                    f"بار در هفته"
                )


            # =================================================
            # INTERVAL
            # =================================================

            else:

                interval_hours = st.number_input(

                    "هر چند ساعت یک‌بار؟",

                    min_value=1,

                    max_value=168,

                    value=8,

                    step=1,

                    key=f"interval_hours_{drug_id}",
                )


                st.session_state.dose_values[
                    drug_id
                ] = {

                    "amount":
                        dose_amount,

                    "unit":
                        dose_unit,

                    "frequency_type":
                        "interval",

                    "frequency_per_day":
                        None,

                    "frequency_per_week":
                        None,

                    "interval_hours":
                        interval_hours,
                }


                st.info(

                    f"💊 "
                    f"{dose_amount:g} "
                    f"{dose_unit} "
                    f"هر "
                    f"{interval_hours} "
                    f"ساعت یک‌بار"
                )


# =========================================================
# ADD ANOTHER DRUG
# =========================================================

if st.session_state.selected_drugs:

    st.divider()

    st.info(

        "برای افزودن داروی دیگر، "
        "نام داروی بعدی را در قسمت جستجوی بالا وارد کنید."
    )


# =========================================================
# FINAL SUMMARY
# =========================================================

if st.session_state.selected_drugs:

    st.divider()

    st.subheader(
        "۳. خلاصه داروهای بیمار"
    )


    for index, drug in enumerate(

        st.session_state.selected_drugs

    ):

        drug_id = drug["id"]


        dose = st.session_state.dose_values.get(
            drug_id
        )


        drug_name = (

            drug.get("brand_name_fa")

            or drug.get("brand_name_en")

            or "-"
        )


        if dose:

            # -------------------------------------------------
            # Daily
            # -------------------------------------------------

            if dose["frequency_type"] == "daily":

                usage_text = (

                    f"{dose['amount']:g} "

                    f"{dose['unit']} "

                    f"در هر نوبت، "

                    f"{dose['frequency_per_day']} "

                    f"بار در روز"
                )


            # -------------------------------------------------
            # Weekly
            # -------------------------------------------------

            elif dose["frequency_type"] == "weekly":

                usage_text = (

                    f"{dose['amount']:g} "

                    f"{dose['unit']} "

                    f"{dose['frequency_per_week']} "

                    f"بار در هفته"
                )


            # -------------------------------------------------
            # Interval
            # -------------------------------------------------

            else:

                usage_text = (

                    f"{dose['amount']:g} "

                    f"{dose['unit']} "

                    f"هر "

                    f"{dose['interval_hours']} "

                    f"ساعت یک‌بار"
                )


            st.write(

                f"**{index + 1}. {drug_name}** — "

                f"{usage_text}"
            )


        else:

            st.write(

                f"**{index + 1}. {drug_name}**"
            )


# =========================================================
# TECHNICAL OUTPUT
# =========================================================

with st.expander(
    "اطلاعات فنی برای توسعه‌دهنده"
):

    final_data = []


    for drug in st.session_state.selected_drugs:

        drug_id = drug["id"]


        dose = st.session_state.dose_values.get(
            drug_id
        )


        final_data.append({

            "drug_id":
                drug_id,

            "brand_name_fa":
                drug.get(
                    "brand_name_fa"
                ),

            "brand_name_en":
                drug.get(
                    "brand_name_en"
                ),

            "generic_name":
                drug.get(
                    "generic_name_en"
                ),

            "form":
                drug.get(
                    "form"
                ),

            "strength":
                drug.get(
                    "strength"
                ),

            "manufacturer":
                drug.get(
                    "manufacturer"
                ),

            "usage":
                dose,
        })


    st.json(
        final_data
    )

