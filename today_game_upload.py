from datetime import datetime, timezone
from flask import jsonify, redirect, render_template_string, request, url_for
from sqlalchemy import inspect, text
import app as app_module
import today_game as today_game_module

app = app_module.app
app.config["MAX_FORM_MEMORY_SIZE"] = 3_000_000
MAX_IMAGE_CHARS = 2_000_000
ALLOWED_IMAGE_PREFIXES = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")

# Store the uploaded image in the existing today_game table so Render does not rely on local disk.
columns = {column["name"] for column in inspect(app_module.engine).get_columns("today_game")}
if "image_data" not in columns:
    with app_module.engine.begin() as connection:
        connection.execute(text("ALTER TABLE today_game ADD COLUMN image_data TEXT DEFAULT ''"))


def _current(db):
    return today_game_module._current(db)


def _image_value(item):
    with app_module.engine.connect() as connection:
        row = connection.execute(
            text("SELECT image_data FROM today_game WHERE id = :id"),
            {"id": item.id},
        ).mappings().first()
    image_data = (row.get("image_data") or "") if row else ""
    return image_data or (item.image_url or "")


def _safe_image_data(value):
    value = (value or "").strip()
    if not value or len(value) > MAX_IMAGE_CHARS:
        return ""
    if not value.startswith(ALLOWED_IMAGE_PREFIXES):
        return ""
    return value


def api_today_game_v2():
    db = app_module.DBSession()
    item = _current(db)
    image = _image_value(item)
    return jsonify({
        "title": item.title or "",
        "image_url": image,
        "cafe_url": item.cafe_url or "",
        "updated_at": item.updated_at or "",
        "enabled": bool(item.title and image and item.cafe_url),
    })


def admin_today_game_v2():
    db = app_module.DBSession()
    item = _current(db)
    error = ""
    existing_image = _image_value(item)

    if request.method == "POST":
        title = app_module.clean_text(request.form.get("title"))[:250]
        image_data = _safe_image_data(request.form.get("image_data"))
        keep_existing = request.form.get("keep_image") == "1"
        cafe_url = today_game_module._safe_cafe_url(request.form.get("cafe_url"))

        if cafe_url is None:
            error = "네이버 카페 주소만 입력해 주세요."
        elif not title:
            error = "게임 이름을 입력해 주세요."
        elif not image_data and not (keep_existing and existing_image):
            error = "대표 이미지를 선택하거나 붙여넣어 주세요."
        elif not cafe_url:
            error = "네이버 카페 글 주소를 입력해 주세요."
        else:
            item.title = title
            item.cafe_url = cafe_url
            item.updated_at = datetime.now(timezone.utc).isoformat()
            if image_data:
                with app_module.engine.begin() as connection:
                    connection.execute(
                        text("UPDATE today_game SET image_data = :image_data, image_url = '' WHERE id = 1"),
                        {"image_data": image_data},
                    )
            db.commit()
            return redirect(url_for("admin_today_game"))

    return render_template_string(ADMIN_HTML, item=item, error=error, existing_image=existing_image)


# Replace the existing views only after today_game.py has loaded successfully.
app.view_functions["api_today_game"] = api_today_game_v2
app.view_functions["admin_today_game"] = admin_today_game_v2


ADMIN_HTML = """<!doctype html>
<html lang='ko'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>오늘의 회원 추천 게임 관리</title>
<style>
body{font-family:system-ui,-apple-system,BlinkMacSystemFont,'Noto Sans KR',sans-serif;background:#f6f3ed;margin:0;color:#29251f}
.wrap{max-width:780px;margin:auto;padding:28px 18px}.panel{background:#fff;border:1px solid #e7e0d5;border-radius:22px;padding:24px;box-shadow:0 8px 30px #0000000b}
.back{display:inline-block;margin-bottom:16px;color:#6a4cff;text-decoration:none}.kicker{display:inline-block;margin-bottom:7px;color:#8a6a20;font-size:12px;font-weight:900;letter-spacing:.08em}
h1{margin:0 0 8px}p{color:#716a61;line-height:1.6}.error{background:#fff0f0;color:#b42318;padding:12px;border-radius:10px;margin:16px 0}
label{display:block;font-weight:800;margin:20px 0 8px}input[type=text],input[type=url]{box-sizing:border-box;width:100%;padding:13px 14px;border:1px solid #d9d1c5;border-radius:12px;font:inherit}
.image-area{border:2px dashed #d7cdbf;border-radius:16px;background:#fbfaf7;padding:18px;text-align:center}.image-area:focus-within{border-color:#9a7cff;box-shadow:0 0 0 4px #8b5cf61a}
.image-buttons{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}.pick{display:inline-flex;align-items:center;justify-content:center;padding:12px 16px;border-radius:12px;background:#29251f;color:#fff;font-weight:900;cursor:pointer;border:0;font:inherit}.pick.secondary{background:#eee8df;color:#29251f}
#imageFile{display:none}.image-help{margin:10px 0 0;color:#82796e;font-size:13px;line-height:1.55}.preview{display:none;margin:16px auto 0;max-width:280px}.preview.show{display:block}.preview img{display:block;width:100%;max-height:360px;object-fit:contain;border-radius:13px;background:#eee}.status{margin-top:10px;font-size:13px;color:#82796e}.status.ok{color:#315c47}
button.save{margin-top:20px;border:0;border-radius:13px;padding:14px 18px;background:#29251f;color:#fff;font-weight:900;font:inherit;cursor:pointer;width:100%}
.current{margin-top:24px;padding:16px;background:#faf8f4;border-radius:15px}.current img{width:100%;max-width:220px;max-height:280px;object-fit:contain;background:#eee;border-radius:13px;display:block;margin:12px 0}.current a{color:#6a4cff;font-weight:800}.hint{font-size:13px;color:#82796e;margin-top:8px}
@media(max-width:560px){.panel{padding:18px}.image-buttons{display:grid;grid-template-columns:1fr 1fr}.pick{padding:13px 8px}}
</style>
</head>
<body>
<main class='wrap'>
<a class='back' href='/admin'>← 관리자 페이지로 돌아가기</a>
<section class='panel'>
<span class='kicker'>TODAY'S GAME</span>
<h1>오늘의 회원 추천 게임</h1>
<p>게임 이름과 대표 이미지만 넣고, 실제 소개 글은 네이버 카페로 연결하세요.</p>
{% if error %}<div class='error'>{{ error }}</div>{% endif %}
<form method='post' id='todayGameForm'>
<input type='hidden' name='_csrf_token' value='{{ csrf_token() }}'>
<input type='hidden' name='image_data' id='imageData'>
<input type='hidden' name='keep_image' id='keepImage' value='1'>
<label for='title'>1. 게임 이름</label>
<input id='title' name='title' type='text' value='{{ item.title }}' placeholder='예: 윙스팬' required>
<label>2. 대표 이미지</label>
<div class='image-area'>
<div class='image-buttons'>
<label class='pick' for='imageFile'>📱 이미지 선택</label>
<button class='pick secondary' type='button' id='pasteButton'>📋 이미지 붙여넣기</button>
</div>
<input id='imageFile' type='file' accept='image/*'>
<p class='image-help'>모바일: 사진첩에서 이미지 선택<br>PC: 이미지를 복사한 뒤 「이미지 붙여넣기」를 누르거나 Ctrl+V</p>
<div id='imageStatus' class='status'>새 이미지를 선택하지 않으면 현재 이미지를 그대로 유지합니다.</div>
<div id='imagePreview' class='preview'><img id='previewImg' alt='대표 이미지 미리보기'></div>
</div>
<label for='cafeUrl'>3. 네이버 카페 글 주소</label>
<input id='cafeUrl' name='cafe_url' type='url' value='{{ item.cafe_url }}' placeholder='https://cafe.naver.com/...' required>
<div class='hint'>홈페이지의 큰 오늘의 회원 추천 게임 카드를 누르면 이 글로 이동합니다.</div>
<button class='save' type='submit'>오늘의 회원 추천 게임 저장</button>
</form>
{% if item.title and existing_image and item.cafe_url %}
<div class='current'><b>현재 오늘의 회원 추천 게임</b><img src='{{ existing_image }}' alt=''><strong>{{ item.title }}</strong><p><a href='{{ item.cafe_url }}' target='_blank' rel='noopener noreferrer'>현재 네이버 카페 글 열기 ↗</a></p></div>
{% endif %}
</section>
</main>
<script>
(() => {
 const fileInput=document.getElementById('imageFile'), dataInput=document.getElementById('imageData'), keepInput=document.getElementById('keepImage');
 const preview=document.getElementById('imagePreview'), previewImg=document.getElementById('previewImg'), status=document.getElementById('imageStatus'), pasteButton=document.getElementById('pasteButton');
 function setImage(file){
   if(!file || !file.type.startsWith('image/')){status.textContent='이미지 파일만 선택해 주세요.';return;}
   const reader=new FileReader();
   reader.onload=()=>compress(reader.result).then(data=>{
     dataInput.value=data; keepInput.value='0'; previewImg.src=data; preview.classList.add('show'); status.className='status ok'; status.textContent='✓ 이미지를 준비했습니다.';
   }).catch(()=>{status.textContent='이미지를 읽지 못했습니다.';});
   reader.readAsDataURL(file);
 }
 function compress(src){
   return new Promise((resolve,reject)=>{
     const img=new Image();
     img.onload=()=>{
       const max=1200, scale=Math.min(1,max/Math.max(img.width,img.height));
       const canvas=document.createElement('canvas'); canvas.width=Math.max(1,Math.round(img.width*scale)); canvas.height=Math.max(1,Math.round(img.height*scale));
       const ctx=canvas.getContext('2d'); ctx.fillStyle='#fff'; ctx.fillRect(0,0,canvas.width,canvas.height); ctx.drawImage(img,0,0,canvas.width,canvas.height);
       resolve(canvas.toDataURL('image/jpeg',.82));
     }; img.onerror=reject; img.src=src;
   });
 }
 fileInput.addEventListener('change',()=>setImage(fileInput.files[0]));
 pasteButton.addEventListener('click',()=>navigator.clipboard?.read?.().then(items=>{
   for(const item of items){const type=item.types.find(t=>t.startsWith('image/')); if(type){item.getType(type).then(blob=>setImage(blob));return;}}
   status.textContent='클립보드에 이미지가 없습니다.';
 }).catch(()=>{status.textContent='브라우저에서 클립보드 접근이 차단되었습니다. Ctrl+V를 사용해 주세요.';}));
 document.addEventListener('paste',e=>{const file=[...(e.clipboardData?.files||[])].find(f=>f.type.startsWith('image/')); if(file){e.preventDefault();setImage(file);}});
})();
</script>
</body>
</html>"""
