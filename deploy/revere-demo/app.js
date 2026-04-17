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

  // CT-0417-25 architecture lock: Chamber admin only ever sees ATLAS speak.
  // Kicker labels name the specialist Atlas is narrating; the voice stays Atlas.
  var AGENT_LABELS = {
    atlas:     'Atlas · Chamber orchestrator',
    hermes:    'Atlas · narrating Hermes (inbound)',
    artemis:   'Atlas · narrating Artemis (outbound)',
    penelope:  'Atlas · narrating Penelope (events)',
    sophia:    'Atlas · narrating Sophia (member success)',
    iris:      'Atlas · narrating Iris (comms)',
    athena:    'Atlas · narrating Athena (Board ops)',
    echo:      'Atlas · narrating Echo (reputation)',
    cleopatra: 'Atlas · narrating Cleopatra (creative)',
    aria:      'Atlas · voice modality'
  };

  // Scripted greetings — every reply spoken AS Atlas, naming the specialist
  // backstage when it adds clarity. Specialists never speak to the admin.
  var GREETINGS = {
    atlas:     "Don — good morning. I'm holding 12 active delegations right now. Sophia is mid-onboarding on two new members, Penelope is closing RSVPs for Wednesday's Small Business Office Hours, Iris ships the monthly newsletter tomorrow. Want a full Board-ready status or just the blockers?",
    hermes:    "Hermes took 214 inbound calls this month — answered inside two rings on every one, tier-1 resolved on 73%. Top three topics: event calendar, member directory access, renewal dates. Want me to have Iris ship a one-page FAQ so Hermes can free up more of your Board's time?",
    artemis:   "I ran Artemis on 96 renewal touches and 47 new-business calls last week. Wins worth flagging: Winthrop Cares wants Silver sponsor tier, Pacini Tile renewed three years, Revere Youth Soccer wants a meeting with you personally. Want me to book Soccer first?",
    penelope:  "Penelope's events board: 4 live, 182 RSVPs tracked, 81% average show rate. Wednesday's Small Business Office Hours is at 34 RSVPs, up 18% from last month. Penelope has the reminder sequence ready — send Monday 9 AM or hold for your final list?",
    sophia:    "Sophia's member lifecycle: 9 onboarded, 4 lapsed re-engaged, 2 at renewal risk — the auto repair shop and the yoga studio, both late-openers. I already queued the warm-call + follow-up email sequence on both. Drafts are in your approvals tray.",
    iris:      "Iris has the April newsletter at 42% open / 11% click-through — healthy above benchmark. May draft is warming with three blocks: Board spotlight, Gala save-the-date, member business of the month. Want to sign off on the spotlight?",
    athena:    "Athena has April Board fully documented — minutes shipped, 12 motions logged, 34 action items with owners. One overdue: Rick's streetscape response memo. Want me to nudge Rick through Iris's Friday reminder loop?",
    echo:      "Echo is watching 127 reviews across the member roster — 14-minute average response, net sentiment +78. Two need your eyes: Joe's 3★ on Yelp (Echo drafted the response, awaiting owner approval) and a 1★ spam flag on Kelly's that Echo already filed with Google.",
    cleopatra: "Cleopatra has shipped 68 creative assets this month, average brand-gate score 9.4, 100% brand-consistency. The Gala save-the-date hero and the May member spotlight banner are ready for your review in the Creative tray.",
    aria:      "Atlas here, on voice. Same brain, same delegation — just speaking through the orb now. Ask me anything: member count, next Board meeting, a quick thank-you draft, a sponsor follow-up. I'll speak the answer and run the specialists silently."
  };

  // Three Atlas-voiced follow-ups per lane — cycled on successive messages.
  // Atlas is always the speaker; specialists are named when it adds clarity.
  var FOLLOW_UPS = {
    atlas: [
      "Routing: Sophia takes the two at-risk renewals, Artemis gets the sponsor re-engagement list, Athena picks up the Board memo, Cleopatra is on the Gala flyer. Everything lands in your approvals tray by 4 PM. Say the word if you want anything bumped direct.",
      "Blocker check — only one: Rick's streetscape memo. I'll ping him through Iris's Friday reminder loop rather than a direct ask. Everything else is self-healing.",
      "I can run a dry-rehearsal for Tuesday's Board meeting — Athena simulates likely questions, pre-briefs you on the three items most likely to provoke discussion. Twelve minutes, done from your phone on voice. Queue it?"
    ],
    hermes: [
      "Hermes's FAQ draft is up: event calendar, renewal dates, member directory, sponsor contact, bilingual support. I routed Cleopatra to render a print-ready flyer version too — expect both in your inbox by 2 PM.",
      "Two Hermes calls this week flagged payment confusion on Corporate tier 3-year billing. I'll have Iris add a Q&A card to the May newsletter clarifying $1,000-for-three-years, effectively $333/yr. Approve?",
      "Hermes is holding 73% tier-1 resolution. Top escalations to you: member-onboarding clarifications and Board-contact routing. Both fixable with a public Board roster page — want me to flag that to Athena for the next meeting?"
    ],
    artemis: [
      "Booked — Revere Youth Soccer League, Wednesday 3 PM, Zoom. Artemis prepped a briefing for you: their ask ($500 jersey patch), our offer (branded jersey + social series on league night), and the pro-bono community-fit angle. It's on your calendar.",
      "Pacini Tile's 3-year renewal paperwork is in the Chamber pack — auto-invoice lined up for the 15th. Nothing for you to do unless they ask for an extension.",
      "Artemis's outbound queue for next week: 6 lapsed members (auto-dialed Tuesday 10 AM), 3 sponsor follow-ups, 2 new-business warm leads from the directory crawl. I'll flag any reply that needs your touch."
    ],
    penelope: [
      "Penelope's reminder sequence is live — Monday 9 AM first touch, Wednesday 8 AM second, day-of text nudge. I'll tune it against last-cycle show rates and report a one-liner after the event.",
      "Gala save-the-date goes Monday. Cleopatra has the hero ready (board vote captured 2026-04-10). Penelope has the RSVP landing page at portal.reverechamber.org/gala — live by Sunday.",
      "Wednesday's Office Hours is at 34 RSVPs against a 60 cap. Penelope has one last reminder queued for Friday 8 AM. If we hit 50 by Monday I'd move the event to Chamber Hall so we don't overcrowd City Hall again."
    ],
    sophia: [
      "Sophia runs both at-risk renewals: warm call from Artemis tomorrow, follow-up email from Sophia 24 hours later. This pattern converts 7 of 9 historically — we catch them before the 30-day auto-lapse.",
      "Sophia's onboarding week-1 check-in for Kelly's Roast Beef is all green. Week-2 she pulls GBP baseline and member directory completeness. Standard playbook, no exceptions.",
      "Sophia's lifecycle dashboard: 92% 12-month retention — above Chamber benchmark (84%). The two lapses this year both cited life events, not program value. She's logged that distinction in the renewal rubric."
    ],
    iris: [
      "Locked: Iris has Marisa at North Shore Dental for Board spotlight (concrete community-dental-day story). Gala save-the-date top block. Member of the month rotates to Kelly's Roast Beef — their 94 GBP score is a tidy proof point.",
      "Iris is running the new-member drip: Day 1 welcome, Day 7 first-event nudge, Day 30 check-in. Open rates 48 / 41 / 37. I'd have her add a Day 60 satisfaction survey if you approve.",
      "Iris's bilingual send is live. Spanish-version subject line beat English by 6 opens last issue — she's keeping that split and testing a second variant next cycle."
    ],
    athena: [
      "Athena's minutes are filed, tagged, searchable, with every motion linked to its action-item owner. The 30-day status check is on auto-fire; Board portal shows current state any time you want it.",
      "Rick's been nudged — he replied he'll ship the memo Friday 5 PM. Athena holds the action-item timer until 5:01 PM and only then escalates.",
      "Athena has a dry-rehearsal queued for Tuesday 9 AM — 12 minutes, phone-only. She'll pre-brief you on the three highest-friction agenda items plus likely Board questions from the last six meetings' pattern."
    ],
    echo: [
      "Echo sent Joe's 3★ response after your approval. She added the incident to the kitchen-review log and queued the Pioli-family follow-up email for Friday. No further action on your side.",
      "Echo reports sentiment stable — Joe's Pizza trending up 0.3★ month-over-month, Kelly's flat, North Shore Auto Body dipped 0.2★ (two legitimate service complaints, both responded to). She'll flag if the dip continues past 2 weeks.",
      "Echo's monthly reputation report for the Board will show 127 reviews monitored, 14-min average response, zero unhandled negatives. Athena and Iris both want the summary — Echo will ship one version each in the format they need."
    ],
    cleopatra: [
      "Cleopatra's slideshow is ready: Gala save-the-date hero, May spotlight banner, Small Business Office Hours flyer, Sponsor-of-the-Month template. All scored 9.3+ by our brand gate against the Chamber brand pack. Want to see them in the Creative tray or have them auto-routed?",
      "Cleopatra's brand-consistency check ran this morning across 68 assets — 100% inside the Chamber pack. One warning: two March flyers used the pre-v4 navy; she queued re-renders, nothing shipped from them this cycle.",
      "For the Gala, Cleopatra recommends our typography-first model for the flyer (legible baked-in text) and our photoreal model for the Chamber-Hall hero. Budget is well inside the May cap — brand gate stays on, no surprises."
    ],
    aria: [
      "Revere Chamber added 9 new members this month. 4 renewals pending, 2 flagged at-risk. Sophia has both at-risk accounts in a warm-touch sequence starting tomorrow. Want me to text you when the first reply comes in?",
      "Sponsor thank-you drafted: 'Kay — thank you for championing the 2026 Revere Chamber Gala. Your support funds the scholarship, the bilingual outreach, and one more year of connecting our business community. We'll see you May 18. — Don Martelli, President.' Send as-is or tweak?",
      "Next Board meeting proposed for Thursday May 7, 6 PM at Chamber Hall. Athena checked the Board's availability — 9 of 11 free, calendars auto-held. She'll prep the agenda draft by Monday. Confirm?"
    ]
  };

  var followCounter = {};

  // Aria quick-prompts map directly to one of Aria's scripted follow-ups
  var ARIA_PROMPT_INDEX = { members: 0, sponsor: 1, board: 2 };

  window.openChat = function(agent, ariaPrompt){
    if (!AGENT_LABELS[agent]) agent = 'atlas';
    currentAgent = agent;
    chatKicker.textContent = AGENT_LABELS[agent];
    chatLog.innerHTML = '';
    followCounter[agent] = 0;
    addAgentMsg(GREETINGS[agent]);
    if (agent === 'aria' && ariaPrompt && ARIA_PROMPT_INDEX[ariaPrompt] != null) {
      var idx = ARIA_PROMPT_INDEX[ariaPrompt];
      var promptText = {
        members: 'How many new members this month?',
        sponsor: 'Draft a sponsor thank-you.',
        board:   'Schedule the next Board meeting.'
      }[ariaPrompt];
      setTimeout(function(){
        addUserMsg(promptText);
        setTimeout(function(){
          addAgentMsg(FOLLOW_UPS.aria[idx]);
          followCounter.aria = idx + 1;
        }, 700);
      }, 500);
    }
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
