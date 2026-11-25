✅ STAGE 2–3 เสร็จสมบูรณ์ — Dice Lab PWA พร้อมใช้งาน
สิ่งที่สร้าง/แก้ไข (ทั้งหมด uncommitted ตาม git status)
ไฟล์	สถานะ	เนื้อหา
server/dice-server.py	แก้	bind 0.0.0.0:7373, engine roll/fusion, async job + progress + live preview, /get?file=, /set?file=, secret redaction, drawdown, run-lock
web/dice-ui.html	แก้	PWA meta + manifest + SW registration, config switcher (dice/fusion), fusion key editor จัดกลุ่ม+ค้นหา, engine selector, progress bar, กราฟ drawdown + donut win/loss, ปุ่มติดตั้งแอป, mobile safe-area + sticky RUN
web/manifest.json	ใหม่	standalone, theme #0a0d14, 3 icons, shortcuts → /?tab=lab, /?tab=calc
web/service-worker.js	ใหม่	cache-first static, network-first API/navigation, POST ไม่ถูก cache, offline JSON fallback
web/icons/	ใหม่	PNG 4 ไฟล์ สร้างด้วย tools/generate_icons.py (stdlib ล้วน)
launch.sh	ใหม่	เริ่มเซิร์ฟเวอร์ + เปิดเบราว์เซอร์ (wslview → cmd.exe /c start → xdg-open), พิมพ์ IP Tailscale/LAN
launch.bat	ใหม่	เวอร์ชัน Windows
ผลทดสอบ (QA บน config สำเนาชั่วคราว — ไฟล์ tracked ไม่ถูกแตะ)
- /ping ✓ · /get?file=fusion → 33 keys, ไม่มี STAKE_API_KEY ✓ (แม้จะ POST พยายามแทรก token ก็ถูกละเว้น, token จริงในไฟล์ไม่เปลี่ยน) ✓
- /run roll mode 2 (seed 42) → 34 รอบ, stop_reason WAGER REACHED, equity+drawdown ครบ ✓
- /run fusion mode 2 (seed 42) → normalize เป็น field เดียวกับ roll, vault=0, 300 รอบ ✓
- Async → job รันพื้นหลัง, poll ได้ preview 394 จุดระหว่างรัน, จบได้ result 614 จุด ✓
- Run-lock → job ที่สองได้ 409 พร้อมข้อความไทย, ปลดล็อกหลังจบ ✓
- /calc → base 0.03444 (n=50), auto-n=14 โหมด risk 0.0001 ✓
- /manifest.json (application/manifest+json), /service-worker.js, icons, /csv?file=latest ✓
- HTML: tag balance 0 error, JS ผ่าน node --check, ไม่มี external URL/CDN เลย, id ครบทุกตัวที่ JS อ้าง ✓
- เซิร์ฟเวอร์พิมพ์ URL Tailscale ให้เอง (เจอ 100.93.45.16, 100.69.181.45 ฯลฯ) ✓
📱 วิธีใช้จากมือถือผ่าน Tailscale
1. เครื่องหลัก: bash launch.sh (หรือ launch.bat บน Windows) — จะพิมพ์ลิงก์ Tailscale และเปิดเบราว์เซอร์ให้เอง
2. มือถือ ที่ล็อกอิน Tailscale วงเดียวกัน: เปิด http://<IP-Tailscale>:7373/
3. ติดตั้งเป็นแอป
- Android/Chrome: เมนู ⋮ → "ติดตั้งแอป" หรือกดปุ่ม 📲 ติดตั้งแอป บนหัวมุม
- iPhone/Safari: ปุ่มแชร์ → "เพิ่มไปที่หน้าจอโฮม"
4. เปิดจากไอคอนแล้วจะได้หน้าจอเต็มแบบ standalone ทำงานแบบ mock/simulation เท่านั้น
⚠️ ตามเดิม: ทุกอย่างรันโหมดจำลอง — ไม่มีส่วนใดใน UI/launcher ที่เรียก --live และ API key ไม่เคยถูกส่งออกจากเซิร์ฟเวอร์