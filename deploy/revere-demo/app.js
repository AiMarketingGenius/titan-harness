// Revere AI Advantage — demo app logic
// Password gate + view router + chat modal with scripted demo responses

(function(){
  'use strict';

  // ---------- PASSWORD GATE ----------
  var PW = 'revere2026';
  var gate = document.getElementById('gate');
  var app = document.getElementById('app');
  var footer = document.getElementById('footer');
  var form = document.getElementById('gate-form');
  var pwIn = document.getElementById('gate-pw');
  var err = document.getElementById('gate-err');

  // Auto-unlock if session already authenticated
  if (sessionStorage.getItem('revere-demo-auth') === 'ok') {
    unlock();
  }

  form.addEventListener('submit', function(e){
    e.preventDefault();
    if (pwIn.value === PW) {
      sessionStorage.setItem('revere-demo-auth', 'ok');
      unlock();
    } else {
      err.hidden = false;
      pwIn.value = '';
      pwIn.focus();
    }
  });

  function unlock(){
    gate.style.display = 'none';
    app.hidden = false;
    footer.hidden = false;
    err.hidden = true;
  }

  // ---------- VIEW ROUTER ----------
  var navButtons = document.querySelectorAll('.nav-btn');
  var views = document.querySelectorAll('.view');
  navButtons.forEach(function(btn){
    btn.addEventListener('click', function(){
      switchView(btn.dataset.view);
    });
  });
  window.switchView = function(target){
    navButtons.forEach(function(b){ b.classList.toggle('active', b.dataset.view === target); });
    views.forEach(function(v){ v.classList.toggle('active', v.dataset.view === target); });
    window.scrollTo({top:0, behavior:'smooth'});
  };

  // ---------- CHAT MODAL ----------
  var modal = document.getElementById('chat-modal');
  var chatLog = document.getElementById('chat-log');
  var chatForm = document.getElementById('chat-form');
  var chatInput = document.getElementById('chat-input');
  var chatKicker = document.getElementById('chat-kicker');
  var currentAgent = 'coach';

  var AGENT_LABELS = {
    coach:    'Revere Business Coach',
    content:  'Revere Content Strategist',
    seo:      'Revere SEO Specialist',
    social:   'Revere Social Media Manager',
    reviews:  'Revere Reviews Manager',
    outbound: 'Revere Outbound Coordinator',
    cro:      'Revere Conversion Optimizer'
  };

  // Scripted demo conversation seeds — chosen to sound real for Joe's Pizza of Revere
  var GREETINGS = {
    coach:    "Hey Joe, ready when you are. Last time we said April's focus was getting the Saturday family-deal flywheel going and prepping a soft pitch to Revere Youth Soccer League. Want a status check or a new ask?",
    content:  "Morning Joe. I've got 3 drafts queued — Friday slice night, Saturday family deal, and the Nonna Pioli profile. Anything you want me to tune on voice, or should I keep shipping?",
    seo:      "Your GBP is sitting at 92/100 and we're first for 'Revere pizza delivery' on mobile. Next gain is probably adding 4 more interior photos and closing out 2 unanswered Q&As. Want me to queue that?",
    social:   "12 posts scheduled across IG + FB + GBP for the next 8 days. Engagement lift this month is +38% vs. March. Any dates you want me to steer clear of — any family stuff, trips?",
    reviews:  "Handled 89 reviews this month, avg response 14 min. One 3★ on Yelp from 2 hours ago is pending your sign-off — draft offers a discount comp. Approve, tweak, or skip?",
    outbound: "Revere Youth Soccer League has opened your email 3 times — looks warm. I've got the pitch drafted: $500 jersey patch sponsor + team pizza party after championships. Want me to send?",
    cro:      "Your homepage bounce rate on mobile is 58% — fixable. Biggest single lift: move the 'Order Online' button above the fold and add a 'Today's Special' strip. I can mock both in 10 min."
  };

  // Three follow-up responses per agent, cycled through — keeps the demo alive for Solon's live screenshare
  var FOLLOW_UPS = {
    coach: [
      "Good call. Here's the move: pitch a 4-week pilot — $500 jersey patch + free team pizza party after championships. I'd frame it as 'Joe's Pizza powering Revere youth.' That angle tends to convert with community-first orgs. Want me to hand this to the Outbound Coordinator to draft?",
      "Short answer: your margin on the Saturday family deal is fine as long as soda is the margin-maker, which it is (78%). Run it hard for 6 weeks, then decide. I'll check it against April foot traffic next Friday.",
      "The 'pre-game the Revere Beach lights' line is doing heavy lifting — it's local, it's atmospheric, and it's yours. Keep the Friday slice night anchored on that visual."
    ],
    content: [
      "Tuned. Dropping 'authentic' and 'delicious' from the Saturday post — too generic. Replacing with 'the 1978 recipe card, pressed into a pan every Saturday by the Pioli brothers.' Shipping in 2 min.",
      "Pushed the Nonna Pioli long-form to Sunday 2pm. FB engagement from your zip peaks 1–4pm Sunday — bigger window than Saturday for a story post.",
      "New draft ready for review — 'Revere Beach sunset slice' for next Thursday. Sunset from Winthrop Ave this week is 7:38pm. Want me to shoot the photo or do you have one?"
    ],
    seo: [
      "Queuing 4 photo uploads (interior + Pioli brothers at oven). Marking 2 open Q&As as done. Expect +3 to +5 on GBP score by Monday.",
      "Citation audit came back clean — 14 fixed, 0 inconsistent. Yelp was the last holdout (wrong closing hour), now synced.",
      "Watching 'Revere pizza near me' — we're #2, Kelly's is #1. We can probably flip that in 10 days if we ship 3 short-form reels. I'll ping the Social Media Manager."
    ],
    social: [
      "Noted — no posts April 19–22, you're at your sister's place. I'll auto-bank 4 evergreen posts in case something breaks.",
      "IG is carrying the month — 11.2K impressions, up from 7.8K. Reels are the driver (5x reach vs. static). Want me to shift 30% of static posts to reels starting next week?",
      "Queued a GBP offer for Mother's Day weekend — 10% off family pies, valid Sat + Sun. You can approve / edit any time from the Member Portal."
    ],
    reviews: [
      "Approved, sending now. Response: 'Hey Mark — sorry to hear the crust was off. That's not our standard. Come back this week, ask for Joe, and the next pie is on us. — Pioli Bros.' Filed the incident for kitchen review.",
      "Got it, holding. I'll resend the approval prompt tomorrow 9am. If we don't respond by end of day tomorrow the 3★ will sink our 4.7 average — just an FYI.",
      "I skipped 2 obvious spam 1★s today (both from accounts with 1 review, same template). Flagged them for Google moderation. Nothing for you to action."
    ],
    outbound: [
      "Sending at 2pm — that's when the league director opens his inbox on non-practice days. I'll CC the Business Coach so we can see the thread.",
      "Pacini Tile replied — wants a catering quote for a 24-person job May 3. I handed this to the Business Coach for pricing, then I'll close the loop.",
      "Winthrop Cares replied 'tell me more' — queued a pricing PDF + 2 sample tray options for Monday 9am send. Watch for a shared draft."
    ],
    cro: [
      "Shipping both mocks in Figma — should land in your inbox in ~10 min. When you pick, I'll push the change live + A/B test it against current for 2 weeks.",
      "Added a hot-jar equivalent and saw where mobile users drop off — it's right after the menu section, before 'Order Online.' Classic scroll-fatigue. The CTA move solves it.",
      "While we're in there — your phone number isn't click-to-call on mobile. 30-second fix. Doing it."
    ]
  };

  var followCounter = {};

  window.openChat = function(agent){
    currentAgent = agent;
    chatKicker.textContent = AGENT_LABELS[agent];
    chatLog.innerHTML = '';
    followCounter[agent] = 0;
    addAgentMsg(GREETINGS[agent]);
    modal.hidden = false;
    setTimeout(function(){ chatInput.focus(); }, 50);
  };

  window.closeChat = function(){
    modal.hidden = true;
    chatInput.value = '';
  };

  // Close on overlay click (but not on inner card)
  modal.addEventListener('click', function(e){
    if (e.target === modal) closeChat();
  });

  chatForm.addEventListener('submit', function(e){
    e.preventDefault();
    var msg = chatInput.value.trim();
    if (!msg) return;
    addUserMsg(msg);
    chatInput.value = '';
    // simulate agent typing
    var typing = document.createElement('div');
    typing.className = 'chat-msg agent typing';
    typing.textContent = AGENT_LABELS[currentAgent] + ' is typing…';
    chatLog.appendChild(typing);
    chatLog.scrollTop = chatLog.scrollHeight;
    setTimeout(function(){
      typing.remove();
      var pool = FOLLOW_UPS[currentAgent];
      var idx = (followCounter[currentAgent] || 0) % pool.length;
      followCounter[currentAgent] = (followCounter[currentAgent] || 0) + 1;
      addAgentMsg(pool[idx]);
    }, 900 + Math.random()*600);
  });

  function addUserMsg(text){
    var el = document.createElement('div');
    el.className = 'chat-msg user';
    el.textContent = text;
    chatLog.appendChild(el);
    chatLog.scrollTop = chatLog.scrollHeight;
  }
  function addAgentMsg(text){
    var el = document.createElement('div');
    el.className = 'chat-msg agent';
    el.textContent = text;
    chatLog.appendChild(el);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  // ESC closes chat
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && !modal.hidden) closeChat();
  });
})();
