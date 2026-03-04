"""
================================================================
  Telegram AI Chatbot - Dual Provider: Gemini + Groq
  Thư viện: pyTelegramBotAPI, google-generativeai, groq, python-dotenv
================================================================
  Chiến lược gọi AI:
    1. Thử Gemini (nếu có GEMINI_API_KEY)
    2. Nếu Gemini lỗi/quota hết → tự động chuyển sang Groq
    3. Nếu cả hai đều lỗi → báo lỗi cho người dùng

  Bạn có thể chỉ cần 1 trong 2 key, hoặc cả 2 đều được.
================================================================
"""

import os
import time
import re
import telebot
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv

# ================================================================
#  BƯỚC 1: NẠP BIẾN MÔI TRƯỜNG
# ================================================================
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")   # Có thể để trống
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")     # Có thể để trống

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ Thiếu TELEGRAM_BOT_TOKEN trong file .env!")
if not GEMINI_API_KEY and not GROQ_API_KEY:
    raise ValueError("❌ Cần ít nhất 1 trong 2: GEMINI_API_KEY hoặc GROQ_API_KEY!")


# ================================================================
#  BƯỚC 2: KHỞI TẠO CÁC CLIENT
# ================================================================
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# --- Khởi tạo Gemini (nếu có key) ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Danh sách Gemini model thử theo thứ tự ưu tiên
    GEMINI_MODELS = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.0-pro"]
else:
    GEMINI_MODELS = []  # Bỏ qua Gemini nếu không có key
    print("[INFO] Không có GEMINI_API_KEY → chỉ dùng Groq")

# --- Khởi tạo Groq (nếu có key) ---
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
if not groq_client:
    print("[INFO] Không có GROQ_API_KEY → chỉ dùng Gemini")

# Groq model dùng mặc định (miễn phí, rất nhanh)
GROQ_MODEL = "llama-3.3-70b-versatile"

# System prompt chung cho cả 2 provider
SYSTEM_PROMPT = (
    "Bạn là một trợ lý AI thân thiện, thông minh và hữu ích. "
    "Hãy trả lời bằng tiếng Việt, ngắn gọn và dễ hiểu. "
    "Nếu không biết câu trả lời, hãy thành thật nói không biết."
)


# ================================================================
#  BƯỚC 3A: HÀM GỌI GEMINI (với retry tự động)
# ================================================================
def goi_gemini(cau_hoi: str) -> str:
    """Thử gọi lần lượt các Gemini model, retry nếu bị rate limit tạm thời."""
    if not GEMINI_MODELS:
        raise RuntimeError("Không có GEMINI_API_KEY")

    prompt = f"{SYSTEM_PROMPT}\n\nNgười dùng hỏi: {cau_hoi}"

    for ten_model in GEMINI_MODELS:
        model = genai.GenerativeModel(ten_model)
        so_lan_thu = 0

        while so_lan_thu <= 1:  # thử tối đa 2 lần mỗi model
            try:
                print(f"[Gemini] Đang dùng: {ten_model}")
                response = model.generate_content(prompt)
                return f"[Gemini/{ten_model}]\n\n{response.text}"

            except Exception as loi:
                loi_str = str(loi)
                # Rate limit tạm thời → chờ rồi retry
                if "429" in loi_str and "retry" in loi_str.lower():
                    cho = 15
                    ket_qua = re.search(r"seconds:\s*(\d+)", loi_str)
                    if ket_qua:
                        cho = int(ket_qua.group(1)) + 2
                    so_lan_thu += 1
                    if so_lan_thu <= 1:
                        print(f"[Gemini] Rate limit, chờ {cho}s...")
                        time.sleep(cho)
                        continue
                # Quota hết hẳn hoặc lỗi khác → chuyển model
                print(f"[Gemini] {ten_model} thất bại: {loi_str[:80]}")
                break

    raise RuntimeError("Tất cả Gemini model đều không khả dụng")


# ================================================================
#  BƯỚC 3B: HÀM GỌI GROQ
# ================================================================
def goi_groq(cau_hoi: str) -> str:
    """Gọi Groq API với model LLaMA. Nhanh và miễn phí."""
    if not groq_client:
        raise RuntimeError("Không có GROQ_API_KEY")

    print(f"[Groq] Đang dùng: {GROQ_MODEL}")

    # Groq dùng định dạng messages (giống OpenAI)
    # "system": định nghĩa tính cách AI
    # "user": câu hỏi của người dùng
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": cau_hoi},
        ],
        temperature=0.7,    # 0=chắc chắn, 1=sáng tạo
        max_tokens=1024,    # giới hạn độ dài câu trả lời
    )

    # Lấy text từ response (khác với Gemini)
    return f"[Groq/{GROQ_MODEL}]\n\n{response.choices[0].message.content}"


# ================================================================
#  BƯỚC 3C: HÀM TỔNG — Thử Gemini trước, fallback sang Groq
# ================================================================
def goi_ai(cau_hoi: str) -> str:
    """
    Điều phối: thử Gemini → nếu thất bại thì thử Groq.
    Raise RuntimeError nếu cả hai đều không khả dụng.
    """
    # Thử Gemini trước (nếu có key)
    if GEMINI_MODELS:
        try:
            return goi_gemini(cau_hoi)
        except RuntimeError:
            print("[INFO] Gemini thất bại → chuyển sang Groq...")

    # Fallback: thử Groq
    if groq_client:
        return goi_groq(cau_hoi)

    raise RuntimeError("Không có AI provider nào khả dụng!")


# ================================================================
#  LỆNH /start
# ================================================================
@bot.message_handler(commands=["start"])
def handle_start(message):
    ten = message.from_user.first_name

    # Hiển thị provider đang hoạt động
    providers = []
    if GEMINI_MODELS: providers.append("Gemini ✨")
    if groq_client:   providers.append("Groq ⚡")
    ds_provider = " + ".join(providers)

    chao = (
        f"👋 Xin chào, *{ten}*!\n\n"
        f"🤖 Tôi là Trợ lý AI sử dụng: *{ds_provider}*\n"
        "Hãy nhắn tin bất kỳ điều gì, tôi sẽ cố gắng giúp bạn!\n\n"
        "Gõ /help để xem hướng dẫn."
    )
    bot.reply_to(message, chao, parse_mode="Markdown")


# ================================================================
#  LỆNH /help
# ================================================================
@bot.message_handler(commands=["help"])
def handle_help(message):
    huong_dan = (
        "📋 *Hướng dẫn sử dụng:*\n\n"
        "▶ /start  — Khởi động và nhận lời chào\n"
        "▶ /help   — Xem hướng dẫn này\n"
        "▶ /status — Kiểm tra trạng thái AI provider\n\n"
        "💬 *Cách dùng:*\n"
        "Chỉ cần gõ bất kỳ câu hỏi nào!\n"
        "Ví dụ: _\"Giải thích machine learning là gì?\"_\n\n"
        "⚡ Powered by Gemini + Groq AI"
    )
    bot.reply_to(message, huong_dan, parse_mode="Markdown")


# ================================================================
#  LỆNH /status — Kiểm tra AI provider đang hoạt động
# ================================================================
@bot.message_handler(commands=["status"])
def handle_status(message):
    gemini_status = "✅ Sẵn sàng" if GEMINI_MODELS else "❌ Không có key"
    groq_status   = "✅ Sẵn sàng" if groq_client   else "❌ Không có key"

    trang_thai = (
        "🔍 *Trạng thái AI Provider:*\n\n"
        f"◈ *Gemini* (Google): {gemini_status}\n"
        f"◈ *Groq* (LLaMA):    {groq_status}\n\n"
        "_Gemini được thử trước, Groq là backup._"
    )
    bot.reply_to(message, trang_thai, parse_mode="Markdown")


# ================================================================
#  XỬ LÝ TIN NHẮN THƯỜNG — Gọi AI
# ================================================================
@bot.message_handler(
    content_types=["text"],
    func=lambda m: not m.text.startswith("/")
)
def handle_ai_message(message):
    cau_hoi = message.text

    # Gửi "Đang xử lý..." ngay để người dùng không chờ trống
    tin_cho = bot.reply_to(message, "⏳ Đang xử lý, vui lòng chờ...")

    try:
        # Gọi AI (Gemini ưu tiên, Groq fallback)
        cau_tra_loi = goi_ai(cau_hoi)

        # Xóa tin "Đang xử lý..." và gửi câu trả lời thật
        bot.delete_message(message.chat.id, tin_cho.message_id)
        bot.reply_to(message, cau_tra_loi)

    except Exception as loi:
        print(f"[LỖI CUỐI] {loi}")
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=tin_cho.message_id,
            text=(
                "⚠️ *Không thể kết nối AI lúc này.*\n\n"
                "Nguyên nhân có thể:\n"
                "• Đã hết quota của tất cả provider\n"
                "• Lỗi mạng hoặc API quá tải\n\n"
                "💡 _Dùng /status để kiểm tra trạng thái._\n"
                "Vui lòng thử lại sau!"
            ),
            parse_mode="Markdown"
        )


# ================================================================
#  VÒNG LẶP CHÍNH
# ================================================================
if __name__ == "__main__":
    print("🚀 Telegram AI Bot (Gemini + Groq) đang khởi động...")
    print(f"   Gemini: {'✅ ' + str(GEMINI_MODELS) if GEMINI_MODELS else '❌ Không có key'}")
    print(f"   Groq:   {'✅ ' + GROQ_MODEL if groq_client else '❌ Không có key'}")
    print("📩 Bot sẵn sàng! Nhấn Ctrl+C để dừng.\n")

    bot.infinity_polling(none_stop=True, interval=0)
