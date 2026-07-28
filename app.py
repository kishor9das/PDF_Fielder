import io
import re
import unicodedata
import fitz  # PyMuPDF
import streamlit as st
from rapidfuzz import fuzz

# ------------------------------------------------------------------------------
# 1. CONSTANTS & REGEX PATTERNS
# ------------------------------------------------------------------------------
BANGLA_DIGITS = "১২৩৪৫৬৭৮৯০"
ENGLISH_DIGITS = "1234567890"
TRANSLATION_TABLE = str.maketrans(BANGLA_DIGITS, ENGLISH_DIGITS)

MAT_PATTERN = re.compile(
    r"(মা\s*ট|মা\s*ট\s*মু\s*ল|মো\s*ট|মো\s*ট\s*মু\s*ল)[\s:-]*((?:[\d\.]+\s*)+)",
    re.IGNORECASE,
)
NUM_PATTERN = re.compile(r"\d+(?:\.\d+)?")
WHITESPACE_PATTERN = re.compile(r"\s+")


# ------------------------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ------------------------------------------------------------------------------
def normalize_text(text: str) -> str:
    """Fixes unicode issues and converts Bangla digits to English digits."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return text.translate(TRANSLATION_TABLE)


def extract_fourth_number_from_mat(text_eng: str) -> float | None:
    normalized_text = WHITESPACE_PATTERN.sub(" ", text_eng)

    for match in MAT_PATTERN.finditer(normalized_text):
        num_part = match.group(2)
        numbers = NUM_PATTERN.findall(num_part)

        if len(numbers) >= 4:
            try:
                return float(numbers[3])
            except ValueError:
                pass

    all_nums = NUM_PATTERN.findall(normalized_text)
    if len(all_nums) >= 4 and any(
        kw in text_eng for kw in ["মাট", "মোট", "mat", "mot"]
    ):
        try:
            return float(all_nums[3])
        except ValueError:
            pass

    return None


def check_location_match(cleaned_text: str, cleaned_target: str) -> bool:
    """Checks location with partial or fuzzy matching."""
    if not cleaned_target:
        return True
    if cleaned_target in cleaned_text:
        return True
    return fuzz.partial_ratio(cleaned_target, cleaned_text) >= 65


# ------------------------------------------------------------------------------
# 3. PAGE CONFIG & CUSTOM CSS
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="PDF Advanced Split & Filter", page_icon="📄", layout="wide"
)

st.markdown(
    """
<style>
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .stApp {
        background: #faf6e9 !important;
        color: #4a4a4a;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        animation: fadeIn 0.5s ease-out;
    }
    
    .header-box { text-align: center; padding: 10px 0 20px 0; }
    .main-title { font-size: 2.2rem; font-weight: 700; color: #383733; }
    .sub-title { color: #7d796e; font-size: 0.95rem; }

    div[data-testid="stColumn"] > div, .stFileUploader {
        background: rgba(255, 255, 255, 0.75) !important;
        border: 1px solid rgba(255, 255, 255, 0.9) !important;
        border-radius: 14px !important;
        padding: 15px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
    }

    .stTextInput > div > div {
        background: rgba(255, 255, 255, 0.85) !important;
        border: 1px solid #e2ded0 !important;
        border-radius: 10px !important;
    }

    label { color: #635f56 !important; font-weight: 600 !important; }

    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #ffffff 0%, #f3efe0 100%) !important;
        color: #4a463d !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        border: 1px solid #e5dfcf !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------
# 4. USER INTERFACE LAYOUT
# ------------------------------------------------------------------------------
st.markdown(
    """
<div class="header-box">
    <div class="main-title">📄 হাফ-পেজ স্প্লিট ও ফিল্টার ড্যাশবোর্ড</div>
    <div class="sub-title">ওপর-নিচ কেটে ফিল্টার করে ১ পাতায় ২টি রেজাল্ট মার্জ করুন</div>
</div>
""",
    unsafe_allow_html=True,
)

col_left, col_right = st.columns([1, 1], gap="medium")

with col_left:
    st.markdown("##### 📂 ১) ফাইল আপলোড")
    uploaded_file = st.file_uploader(
        "আপনার মূল পিডিএফ ফাইলটি আপলোড করুন",
        type=["pdf"],
        label_visibility="collapsed",
    )

    st.markdown("##### 🔍 ২) টেক্সট ফিল্টার")
    duplicate_text_input = st.text_input(
        "নির্দিষ্ট শব্দ/লেখা (যেমন: Duplicate):",
        value="",
        placeholder="হাফ-পাতায় এই লেখা থাকলে বাদ যাবে",
    )

    location_input = st.text_input(
        "জায়গার নাম (মিল থাকা হাফ-পাতা রাখা হবে):",
        value="",
        placeholder="যেমন: ঢাকা / Chittagong",
    )

with col_right:
    st.markdown("##### 🔢 ৩) নম্বর ফিল্টার (শুধুমাত্র ৪র্থ সংখ্যার জন্য)")
    min_val_input = st.text_input(
        "নির্দিষ্ট সংখ্যা (৪র্থ সংখ্যাটি সমান বা কম হলে বাদ):",
        value="",
        placeholder="যেমন: 482.76",
    )

    specific_vals_input = st.text_input(
        "কমা দিয়ে একাধিক সংখ্যা (৪র্থ সংখ্যার সাথে হুবহু মিললে বাদ):",
        value="",
        placeholder="যেমন: 482.76, 500, 250",
    )

    st.markdown("##### ⚡ ৪) কুইক প্রায়োরিটি চেকবক্স (অগ্রাধিকার দিতে টিক দিন)")
    chk_col1, chk_col2, chk_col3 = st.columns(3)
    with chk_col1:
        chk_market = st.checkbox("🛒 মার্কেট রিটার্ন")
    with chk_col2:
        chk_b2b = st.checkbox("📦 বিটুবি অর্ডার")
    with chk_col3:
        chk_expiry = st.checkbox("⏳ মেয়াদ উত্তীর্ণ")

    st.markdown("<br>", unsafe_allow_html=True)
    b_col1, b_col2 = st.columns([2, 1])
    with b_col1:
        process_btn = st.button("🚀 প্রসেস এবং মার্জ করুন")
    with b_col2:
        clear_btn = st.button("🔄 রিসেট")

if clear_btn:
    st.rerun()

# ------------------------------------------------------------------------------
# 5. CORE PROCESSING LOGIC
# ------------------------------------------------------------------------------
if uploaded_file is not None and process_btn:
    try:
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_original_pages = len(doc)

        first_page = doc[0]
        orig_width = first_page.rect.width
        orig_height = first_page.rect.height
        half_height = orig_height / 2.0

        progress_bar = st.progress(0)
        status_text = st.empty()

        # STEP A: Split all pages into half-pages
        all_halves = []
        total_steps = total_original_pages
        for page_num in range(total_original_pages):
            progress_bar.progress((page_num + 1) / total_steps)
            status_text.text(f"ধাপ ১ (মাঝ বরাবর কাটছে): পেজ {page_num + 1} / {total_original_pages}")

            page = doc[page_num]
            w = page.rect.width
            h = page.rect.height
            mid_h = h / 2.0

            top_rect = fitz.Rect(0, 0, w, mid_h)
            bot_rect = fitz.Rect(0, mid_h, w, h)

            for rect in [top_rect, bot_rect]:
                raw_text = page.get_text("text", clip=rect) or ""
                text_eng = normalize_text(raw_text)
                clean_text_no_space = WHITESPACE_PATTERN.sub("", text_eng)
                
                all_halves.append({
                    "page_num": page_num,
                    "rect": rect,
                    "raw_text": raw_text,
                    "text_eng": text_eng,
                    "clean_text_no_space": clean_text_no_space,
                    "clean_text_lower": clean_text_no_space.lower()
                })

        # STEP B: Apply Text Filter
        clean_search_term = (
            WHITESPACE_PATTERN.sub("", duplicate_text_input.strip().lower())
            if duplicate_text_input.strip()
            else ""
        )
        clean_target_loc = (
            WHITESPACE_PATTERN.sub("", normalize_text(location_input.strip()))
            if location_input.strip()
            else ""
        )

        part_b_pool = []
        for h_item in all_halves:
            should_delete = False
            if clean_search_term and clean_search_term in h_item["clean_text_lower"]:
                should_delete = True

            if not should_delete and clean_target_loc:
                if not check_location_match(h_item["clean_text_no_space"], clean_target_loc):
                    should_delete = True

            if not should_delete:
                part_b_pool.append(h_item)

        # STEP C: Apply Quick Priority Checkboxes independently from Part B
        quick_keywords = []
        if chk_market:
            quick_keywords.append("টার্ন")
        if chk_b2b:
            quick_keywords.append("অর্ডার")
        if chk_expiry:
            quick_keywords.extend(["উত্তী", "আউট", "শেষ", "অনবো", "ক্ষতিগ্রস্থ", "MRP"])

        priority_pool = []
        if quick_keywords:
            for h_item in part_b_pool:
                is_match = False
                for kw in quick_keywords:
                    normalized_kw = WHITESPACE_PATTERN.sub("", normalize_text(kw)).lower()
                    if normalized_kw in h_item["clean_text_lower"]:
                        is_match = True
                        break
                if is_match:
                    priority_pool.append(h_item)

        # STEP D: Apply Number Filter independently from Part B
        min_val_cleaned = normalize_text(min_val_input.strip())
        min_val = float(min_val_cleaned) if min_val_cleaned else None

        specific_vals = set()
        if specific_vals_input.strip():
            cleaned_spec_input = normalize_text(specific_vals_input)
            for x in cleaned_spec_input.split(","):
                x_str = x.strip().replace(" ", "")
                if x_str:
                    try:
                        specific_vals.add(float(x_str))
                    except ValueError:
                        pass

        number_filtered_pool = []
        if min_val is not None or len(specific_vals) > 0:
            for h_item in part_b_pool:
                fourth_num = extract_fourth_number_from_mat(h_item["text_eng"])
                if fourth_num is not None:
                    if min_val is not None and fourth_num <= min_val:
                        continue
                    if len(specific_vals) > 0 and fourth_num in specific_vals:
                        continue
                number_filtered_pool.append(h_item)

        # Combining results from both independent filters without duplication
        combined_dict = {}
        # If user selected priority checkboxes, add them
        if quick_keywords:
            for item in priority_pool:
                key = (item["page_num"], item["rect"].y0, item["rect"].y1)
                combined_dict[key] = item
        
        # If user provided number filters, add them
        if min_val is not None or len(specific_vals) > 0:
            for item in number_filtered_pool:
                key = (item["page_num"], item["rect"].y0, item["rect"].y1)
                combined_dict[key] = item

        # If neither filter was specified, fall back to entire part_b_pool
        if not quick_keywords and min_val is None and len(specific_vals) == 0:
            final_valid_halves = part_b_pool
        else:
            final_valid_halves = list(combined_dict.values())

        progress_bar.empty()
        status_text.empty()

        # STEP E: Merge Halves into Output Pages
        out_doc = fitz.open()
        total_matched = len(final_valid_halves)

        for i in range(0, total_matched, 2):
            new_page = out_doc.new_page(width=orig_width, height=orig_height)

            item1 = final_valid_halves[i]
            target_rect_top = fitz.Rect(0, 0, orig_width, half_height)
            new_page.show_pdf_page(target_rect_top, doc, item1["page_num"], clip=item1["rect"])

            if i + 1 < total_matched:
                item2 = final_valid_halves[i + 1]
                target_rect_bot = fitz.Rect(0, half_height, orig_width, orig_height)
                new_page.show_pdf_page(target_rect_bot, doc, item2["page_num"], clip=item2["rect"])

        st.markdown("---")
        total_pages = -(-total_matched // 2)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("মূল পেজ সংখ্যা", f"{total_original_pages} টি")
        m2.metric("পাট (বি) ফিল্টারকৃত", f"{len(part_b_pool)} টি")
        m3.metric("চূড়ান্ত নির্বাচিত", f"{total_matched} টি")
        m4.metric("চূড়ান্ত আউটপুট পেজ", f"{total_pages} টি")

        if total_matched > 0:
            out_bytes = out_doc.tobytes()
            file_size_kb = len(out_bytes) / 1024
            
            original_name = uploaded_file.name
            if "." in original_name:
                name_part, ext_part = original_name.rsplit(".", 1)
            else:
                name_part, ext_part = original_name, "pdf"
            
            import random
            random_suffix = random.randint(1, 9)
            download_filename = f"{name_part}_{random_suffix}.{ext_part}"
            
            st.success(f"✨ সফলভাবে প্রসেস সম্পন্ন হয়েছে! (ফাইলের সাইজ: {file_size_kb:.1f} KB)")
            
            st.download_button(
                label="📥 মার্জ করা পিডিএফ ডাউনলোড করুন",
                data=out_bytes,
                file_name=download_filename,
                mime="application/pdf",
            )
        else:
            st.warning(
                "⚠️ আপনার দেওয়া শর্ত অনুযায়ী কোনো হাফ-পেজ খুঁজে পাওয়া যায়নি।"
            )

    except Exception as e:
        st.error(f"❌ একটি সমস্যা হয়েছে: {str(e)}")