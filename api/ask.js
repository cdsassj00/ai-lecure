// Vercel 서버 함수: 강의 콘텐츠 지도의 "AI에게 질문" → OpenRouter 중계.
// 키는 Vercel 프로젝트 환경변수에만 둔다 (브라우저로 내려가지 않음).
//   OPENROUTER_API_KEY  (필수)
//   OPENROUTER_MODEL    (선택, 기본 anthropic/claude-sonnet-5)
//   ASK_PASSCODE        (권장) 설정하면 이 비밀번호를 보낸 요청만 답한다 — 공개 주소에서 키 도용 방지
export const config = { runtime: 'edge' };

const SYSTEM =
  '너는 강사 신성진(CDSA)의 강의안 아카이브를 읽고 답하는 조수다. ' +
  '사용자가 준 [번호] 자료만 근거로 한국어 합니다체로 답하고, 근거가 된 문장 끝에 [번호]를 붙인다. ' +
  '자료에 없는 내용은 추측하지 말고 "기존 강의안에는 없습니다"라고 밝힌다.';

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json; charset=utf-8' } });

export default async function handler(req) {
  if (req.method !== 'POST') return json({ error: 'method', message: 'POST만 받습니다.' }, 405);
  const key = process.env.OPENROUTER_API_KEY;
  if (!key) return json({ error: 'no_key', message: 'Vercel 환경변수 OPENROUTER_API_KEY가 설정되지 않았습니다.' }, 503);

  let body;
  try { body = await req.json(); } catch { return json({ error: 'bad_json', message: '요청 형식이 잘못됐습니다.' }, 400); }
  const need = process.env.ASK_PASSCODE;
  if (need && body?.passcode !== need) return json({ error: 'passcode', message: '질문 비밀번호가 필요합니다.' }, 401);
  const prompt = typeof body?.prompt === 'string' ? body.prompt : '';
  if (!prompt.trim() || prompt.length > 60000) return json({ error: 'bad_prompt', message: '질문이 비었거나 너무 깁니다.' }, 400);

  const model = process.env.OPENROUTER_MODEL || 'anthropic/claude-sonnet-5';
  const up = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${key}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': new URL(req.url).origin,
      'X-Title': 'Lecture Content Map',
    },
    body: JSON.stringify({
      model,
      stream: true,
      max_tokens: 2500,
      messages: [{ role: 'system', content: SYSTEM }, { role: 'user', content: prompt }],
    }),
  });
  if (!up.ok || !up.body) {
    const detail = (await up.text().catch(() => '')).slice(0, 400);
    return json({ error: 'upstream', status: up.status, message: `OpenRouter 오류 ${up.status}`, detail }, 502);
  }
  return new Response(up.body, {
    headers: { 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache', 'X-Model': model },
  });
}
