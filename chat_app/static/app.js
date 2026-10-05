const $ = (id) => document.getElementById(id);
let profiles = [], current = null, session = null, busy = false, generation = 0;
const titleCase = (role) => role.charAt(0) + role.slice(1).toLowerCase();
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type':'application/json', ...(session ? {'X-CSRF-Token':session.csrf_token} : {}), ...options.headers}});
  const data = await response.json();
  if (!response.ok) { const error = new Error(typeof data.detail === 'string' ? data.detail : 'Request could not be completed'); error.status = response.status; throw error; }
  return data;
}
function renderMessage(message) {
  const box = document.createElement('div'); box.className = 'message ' + message.role;
  if (message.role === 'assistant') { const label = document.createElement('span'); label.className = 'message-label'; label.textContent = 'PIED PIPER ASSISTANT'; box.append(label); }
  const content = document.createElement('span');
  if (message.role === 'assistant') {
    for (const token of message.text.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/g)) {
      if (token.startsWith('**') && token.endsWith('**')) { const strong=document.createElement('strong');strong.textContent=token.slice(2,-2);content.append(strong); }
      else if (token.startsWith('`') && token.endsWith('`')) { const code=document.createElement('code');code.textContent=token.slice(1,-1);content.append(code); }
      else content.append(document.createTextNode(token));
    }
  } else content.textContent = message.text;
  box.append(content);
  if (message.actions?.length) { const actions = document.createElement('div'); actions.className='actions'; for (const item of message.actions) { const chip=document.createElement('span'); chip.className='action' + (item.status === 'Completed' ? '' : ' denied'); chip.textContent=item.name.replaceAll('_',' ') + ' · ' + item.status; actions.append(chip); } box.append(actions); }
  $('messages').append(box); $('conversation').scrollTop=$('conversation').scrollHeight;
}
function controls() {
  $('send').disabled=busy || !session; $('prompt').disabled=busy || !session;
  $('new-chat').disabled=busy || !session; $('logout').disabled=busy || !session;
  for (const button of $('profiles').children) button.disabled=busy;
}
function showSession() {
  $('heading').textContent=current.name + '’s workspace'; $('identity').textContent=titleCase(current.role) + ' · Authenticated';
  $('prompt').placeholder='Ask about your work, or ask me to take an action…'; $('messages').replaceChildren();
  $('welcome').hidden=session.messages.length > 0;
  if (!session.messages.length) $('welcome').querySelector('.muted').textContent='You’re chatting as ' + current.name + '.';
  for (const message of session.messages) renderMessage(message);
  $('examples').replaceChildren();
  const examples = current.role === 'EMPLOYEE' ? ['Show my open tasks','Log 7 hours on Compression Engine today','Open a ticket for my VPN issue'] : ['Show requests waiting for my approval','Assign a task to Dinesh to investigate compression performance','Show recent MCP activity'];
  for (const example of examples) { const button=document.createElement('button'); button.textContent=example; button.onclick=()=>{$('prompt').value=example; $('prompt').focus();}; $('examples').append(button); }
  for (const button of $('profiles').children) button.classList.toggle('selected', button.dataset.id === current.id);
}
async function select(profile, fresh=false) {
  if (busy) return;
  busy=true; controls(); $('notice').textContent=''; const ticket=++generation;
  try {
    let next;
    if (!fresh) { try { next=await api('/chat/session/'+profile.id); } catch(error) { if (error.status !== 401) throw error; } }
    if (!next) next=await api('/chat/login',{method:'POST',body:JSON.stringify({profile_id:profile.id})});
    if (ticket !== generation) return;
    current=profile; session=next; localStorage.setItem('pied-chat-profile',profile.id); showSession();
  } catch(error) { $('notice').textContent=error.message; } finally {busy=false;controls();}
}
$('composer').onsubmit=async(event)=>{
  event.preventDefault(); const text=$('prompt').value.trim(); if (!text || busy || !session) return;
  busy=true;controls();$('notice').textContent='';$('welcome').hidden=true;
  const user={role:'user',text}; renderMessage(user); session.messages.push(user); $('prompt').value='';
  const thinking=document.createElement('div');thinking.className='thinking';thinking.textContent='Working on your request…';$('messages').append(thinking);
  try { const result=await api('/chat/message/'+current.id,{method:'POST',body:JSON.stringify({text,turn_id:crypto.randomUUID()})}); thinking.remove();session.messages.push(result.message);renderMessage(result.message); }
  catch(error){thinking.remove();$('notice').textContent=error.message + '. If the connection was interrupted, check the portal before repeating a write.';}
  finally {busy=false;controls();$('prompt').focus();}
};
$('prompt').addEventListener('keydown',(event)=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();$('composer').requestSubmit();}});
$('new-chat').onclick=()=>select(current,true);
$('logout').onclick=async()=>{try{await api('/chat/logout/'+current.id,{method:'POST'});session=null;current=null;localStorage.removeItem('pied-chat-profile');$('messages').replaceChildren();$('examples').replaceChildren();$('welcome').hidden=false;$('identity').textContent='Select a profile to begin';$('heading').textContent='Your work, in conversation.';for(const button of $('profiles').children)button.classList.remove('selected');controls();}catch(error){$('notice').textContent=error.message;}};
async function init(){try{const data=await api('/chat/profiles');profiles=data.profiles;for(const profile of profiles){const button=document.createElement('button');button.className='profile';button.dataset.id=profile.id;button.setAttribute('aria-label','Chat as '+profile.name);const avatar=document.createElement('span');avatar.className='avatar';avatar.textContent=profile.name.split(' ').map(n=>n[0]).join('').slice(0,2);const info=document.createElement('span');const name=document.createElement('span');name.className='profile-name';name.textContent=profile.name;const role=document.createElement('span');role.className='profile-role';role.textContent=titleCase(profile.role)+' · '+profile.department;info.append(name,role);button.append(avatar,info);button.onclick=()=>select(profile);$('profiles').append(button);}const saved=profiles.find(p=>p.id===localStorage.getItem('pied-chat-profile'));if(saved)await select(saved);if(location.hostname==='localhost'||location.hostname==='127.0.0.1')$('portal').href='http://localhost:3300';}catch(error){$('notice').textContent='Could not load profiles: '+error.message;}}
init();
