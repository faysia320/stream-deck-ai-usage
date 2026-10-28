# Codex·Claude Stream Deck 사용량 표시

Windows Stream Deck에 Codex와 Claude 버튼을 각각 추가합니다. 기본 화면에는 5시간·7일 사용률이 표시되고, 버튼을 누르면 리셋 시각 화면으로 전환됩니다. 다시 누르면 사용률로 돌아갑니다. 누를 때 즉시 새로 읽고, 평소에는 1분마다 갱신합니다.

표시 방식은 버튼마다 고를 수 있습니다. Stream Deck 앱에서 버튼을 선택하고 아래 설정의 **표시 방식**에서 고릅니다.

- **숫자** (기본): 장식 배경과 테두리 없이 흰 글씨만 표시합니다. 사용률 숫자는 큰 크기로 표시됩니다.
- **그래프**: 5시간·7일 사용률을 가로 막대로 표시합니다. 라벨과 숫자를 막대 안에 숫자 모드와 비슷한 크기로 넣어 작은 키에서도 읽을 수 있습니다. 막대 색은 70% 미만이면 초록, 70% 이상은 주황, 90% 이상은 빨강입니다.

**타이틀 표시**를 끄면 `CLAUDE`·`CODEX` 글자를 숨기고 그 자리까지 사용량을 더 크게 표시합니다. 기본값은 켜짐입니다.

어느 방식이든 버튼을 누르면 리셋 시각 화면으로 전환됩니다.

### 글꼴

키의 글자는 JetBrains Mono Bold(SIL OFL 1.1)의 글자 모양을 도형으로 그립니다. Stream Deck은 SVG 글자를 브라우저와 다른 글꼴로 그려 글자가 칸을 넘칠 수 있기 때문입니다. 글자마다 폭을 계산해 칸보다 길면 크기를 줄입니다.

다른 글꼴로 바꾸려면 fontTools를 설치하고 글꼴 파일(`.ttf`·`.otf`·`.woff`)을 지정해 글자 모양을 다시 만듭니다. 그다음 `install.ps1`로 다시 설치합니다.

```powershell
python -m pip install fonttools
python .\tools\build_glyphs.py C:\path\to\Font-Bold.ttf
```

글꼴을 바꾸면 `com.local.aiusage.sdPlugin\glyphs-LICENSE.txt`도 그 글꼴의 라이선스로 바꿉니다. 고정폭 글꼴은 글자 폭이 넓어 같은 칸에서 숫자가 조금 작아질 수 있습니다.

## 설치

1. Python 3.10 이상, Elgato Stream Deck 6.6 이상, Claude Code 2.1.251 이상을 준비합니다. Codex 사용량에는 ChatGPT 계정으로 로그인된 Codex CLI가 필요합니다.
2. 이 폴더에서 PowerShell을 열고 `powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1`을 실행합니다.
3. Stream Deck 앱을 종료 후 다시 켭니다. 오른쪽의 **AI Usage**에서 **Codex 사용량**과 **Claude 사용량**을 키에 끌어 놓습니다.
4. Claude Code에 로그인돼 있으면 Claude 사용량이 바로 나타납니다. 로그인 정보를 읽을 수 없으면 Claude Code에서 한 번 요청을 보낸 뒤 나타납니다. Codex는 이 PC에서 Codex 작업을 진행해 세션 기록에 한도 정보가 남으면 표시됩니다.

설치기는 기존 Claude 상태 표시 명령을 래퍼로 덮어쓰지 않습니다. 구버전 래퍼가 설정돼 있으면 저장된 원래 명령 또는 `.claude/settings.json.aiusage-backup-*` 백업에서 복구합니다. 기존 `statusline-command.sh`에 Stream Deck 연결 단계가 있는 경우에는 `collector.py claude-stdin`을 직접 호출하도록 고칩니다. 변경 전 파일은 `.aiusage-repair-*`로 백업합니다. Claude 설정을 건드리지 않으려면 `-NoClaude`를 붙여 설치하세요. Claude 사용량 API 조회를 끄고 상태 표시 입력만 쓰려면 `-NoClaudeApi`를 붙여 설치하세요.

실행용 파일은 `%APPDATA%\Elgato\StreamDeck\Plugins\com.local.aiusage.sdPlugin`에 복사됩니다. 소스 수정 후 `install.ps1`을 실행하고 Stream Deck을 완전히 종료 후 다시 시작하면 수정본이 적용됩니다.

새 환경에서 사용자 상태 표시 스크립트에 연결하려면, JSON 입력을 읽은 뒤 `printf '%s' "$input" | python /설치경로/collector.py claude-stdin >/dev/null 2>&1`을 추가하세요. 경로는 슬래시를 사용합니다. `settings.json`의 상태 표시 명령은 기존 값을 유지합니다.

## 데이터와 한계

- **Claude**: 두 출처를 함께 씁니다. 두 출처 모두 비율과 리셋 시각만 `%LOCALAPPDATA%\AIUsageStreamDeck\claude.json`에 저장하며, 더 최근에 받은 값이 표시됩니다. Claude 데스크톱 앱·웹·Claude Code 사용량은 같은 한도에 합산되므로 어느 쪽에서 쓴 양도 반영됩니다.
  1. **사용량 API**: Claude Code의 `/usage`가 쓰는 `https://api.anthropic.com/api/oauth/usage`를 1분마다 조회합니다. Claude Code가 터미널에서 실행 중이지 않아도 됩니다. 인증에는 Claude Code가 저장한 `%USERPROFILE%\.claude\.credentials.json`의 액세스 토큰을 **읽기만** 합니다. 토큰을 갱신하거나 파일에 쓰지 않으므로 Claude Code 로그인에 영향을 주지 않습니다. 토큰은 저장하거나 로그에 남기거나 플러그인에 넘기지 않습니다. 이 endpoint는 문서화되지 않은 내부 API라 예고 없이 바뀔 수 있습니다.
  2. **상태 표시 입력**: 공식 상태 표시 입력의 `rate_limits.five_hour`와 `rate_limits.seven_day`를 사용합니다. Pro/Max 로그인 계정에서 첫 응답 이후 제공됩니다. 상태 표시 입력 자체는 저장하지 않습니다.

  토큰이 만료됐거나 API 조회가 실패하면 상태 표시 입력으로 받은 값을 씁니다. 토큰은 Claude Code를 쓰면 Claude Code가 갱신합니다. 401·403 응답 뒤에는 5분, 429 응답 뒤에는 `Retry-After`만큼 조회를 쉽니다. 버튼을 연달아 눌러도 API는 30초에 한 번만 부릅니다. 두 출처 모두 1시간 이상 새 값이 없으면 `사용량 없음`으로 표시합니다.
- **Codex**: 공식 Codex app-server의 `account/rateLimits/read`를 사용합니다. 로그인된 Codex CLI 계정에서 현재 사용률과 리셋 시각을 1분마다 직접 읽으므로, 터미널이나 Codex 작업이 실행 중일 필요가 없습니다. Codex 데스크톱 앱 업데이트로 CLI 설치 경로가 바뀌어도 현재 실행 파일을 다시 찾습니다. 5시간·7일 한도 중 계정에서 제공하는 항목만 표시합니다. Codex CLI에 로그인돼 있지 않거나 서비스 조회가 실패하면 `--`로 표시합니다. 버튼 숫자는 **사용한 비율**입니다. 예를 들어 `62%`면 남은 비율은 약 `38%`입니다.
- 수집기는 API 키나 세션 토큰을 저장하지 않습니다. Codex는 Codex CLI의 기존 로그인으로 app-server가 공식 서비스에 조회합니다. Claude는 위에 적은 대로 Claude Code의 액세스 토큰을 메모리에서만 읽어 씁니다. Stream Deck 플러그인은 사용률·리셋 시각만 받습니다. 오류 상세와 원본 응답도 로그에 남기지 않습니다.
- API 과금/토큰 사용량은 로그인 구독의 5시간·주간 한도와 별개입니다.

`python .\collector.py collect`로 플러그인에 전달될 숫자만 확인할 수 있습니다. `null`은 해당 한도를 이 경로에서 확인할 수 없다는 뜻입니다.

Claude 상태 표시줄과 Stream Deck 사용량이 특정 레포에서만 함께 사라지면 그 레포의 `.claude/settings.json` 또는 `.claude/settings.local.json`에 `statusLine`이 있는지 확인하세요. 프로젝트 설정은 사용자 전역 설정보다 우선합니다. 레포에 지정된 명령이 없어진 파일을 가리킨다면 개인용 `.claude/settings.local.json`에 정상 상태 표시 명령을 지정하세요. 사용량 API 조회가 실패할 때는 상태 표시 입력에서 Claude 사용량을 받으므로 해당 명령이 실행되어야 사용량이 갱신됩니다.

제거하려면 `powershell -NoProfile -ExecutionPolicy Bypass -File .\uninstall.ps1`을 실행하고 Stream Deck을 다시 시작합니다. 제거기는 Claude 상태 표시 명령을 이전 값으로 되돌립니다.

## 근거

- [Claude Code 공식 상태 표시 입력](https://code.claude.com/docs/en/statusline): 사용률, 리셋 시각, 값이 생략되는 조건.
- [Codex 공식 개발자 명령](https://learn.chatgpt.com/docs/developer-commands?surface=cli): `/status`와 상태 줄의 사용량 표시.
- [Codex app-server 공식 문서](https://learn.chatgpt.com/docs/app-server): `account/rateLimits/read` 조회와 응답 형식.
- [Elgato 공식 ChatGPT & Codex 소개](https://www.elgato.com/eu/en/explorer/products/stream-deck/control-chatgpt-and-codex-from-stream-deck/): 데스크톱 앱 연동과 사용량 표시.
- [Elgato Stream Deck 플러그인 프로토콜](https://docs.elgato.com/streamdeck/sdk/references/websocket/plugin/): 버튼 제목 갱신.
