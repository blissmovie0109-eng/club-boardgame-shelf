# 동아리 아지트 보드게임 목록

동아리 회원들이 로그인 없이 아지트 보유 보드게임을 확인하고, 관리자는 BoardLife 게임 URL을 붙여넣거나 직접 입력해 목록을 관리하는 Flask 웹사이트입니다.

## 주요 기능
- 공개 게임 목록 / 검색
- 인원수·플레이시간 필터
- 조건에 맞는 게임 랜덤 선택
- 관리자 비밀번호 로그인
- BoardLife 상세 URL 자동 가져오기
- 직접 추가 / 수정 / 삭제
- 로컬 SQLite, 배포 시 PostgreSQL(Neon/Supabase) 지원

## Render 배포
저장소 루트의 `render.yaml`을 이용해 Blueprint로 배포할 수 있습니다.

필수 환경변수:
- `ADMIN_PASSWORD`: 관리자 비밀번호
- `DATABASE_URL`: PostgreSQL 연결 문자열

`SECRET_KEY`는 Render 설정에서 자동 생성되도록 구성되어 있습니다.

배포 후 `/health`에서 `{"ok": true}`가 반환되는지 확인하세요.

## 보안
`.env`, 데이터베이스 비밀번호, 관리자 비밀번호를 GitHub에 커밋하지 마세요.
