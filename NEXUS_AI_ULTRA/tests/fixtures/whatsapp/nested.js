function nestedWhatsAppFixture(){
 for(const [id,testid] of [['search','chat-list-search'],['composer','conversation-compose-box-input']]){
  const input=document.getElementById(id),wrapper=document.createElement('div');
  wrapper.dataset.testid=testid;input.replaceWith(wrapper);wrapper.append(input);
 }
 const title=document.querySelector('#main header span');title.dataset.testid='conversation-info-header-chat-title';title.removeAttribute('title');
 const profile=document.createElement('span');profile.title='Profile details';profile.dir='auto';profile.textContent='Profile';title.before(profile);
 for(const row of document.querySelectorAll('.message-in,.message-out')){
  const content=document.createElement('div');content.dataset.id=row.dataset.id;delete row.dataset.id;
  content.append(...row.childNodes);row.append(content);
  const quote=document.createElement('div');quote.dataset.testid='quoted-message';quote.dataset.id='false_999999999999@c.us_QUOTED';content.append(quote);
  row.classList.remove('message-in','message-out');row.setAttribute('role','row');
 }
 return true;
}
