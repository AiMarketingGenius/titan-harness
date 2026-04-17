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
    atlas:     'Atlas · Chamber OS Orchestrator',
    hermes:    'Hermes · Voice Concierge',
    artemis:   'Artemis · Outbound Voice',
    penelope:  'Penelope · Events Engine',
    sophia:    'Sophia · Member Success',
    iris:      'Iris · Communications',
    athena:    'Athena · Board Ops',
    echo:      'Echo · Reputation Monitor',
    cleopatra: 'Cleopatra · Creative Engine',
    aria:      'Aria · Voice Orb + Mobile Command'
  };

  // Scripted Chamber-facing greetings — each agent speaks in its own lane
  var GREETINGS = {
    atlas:     "Don — good morning. I'm holding 12 active delegations across the team: Sophia is mid-onboarding on two new members, Penelope is closing RSVPs for the Small Business Office Hours, Iris ships the monthly newsletter tomorrow. Want a full Board-ready status or just the blockers?",
    hermes:    "Chamber front desk, on the record. I've answered 214 member calls this month — 73% resolved without escalation. Top three questions this week: event calendar, member directory access, and renewal dates. Want me to draft a one-page FAQ for the site so I can free up more of the Board's time?",
    artemis:   "I ran 96 renewal touches and 47 new-business calls last week. Quick wins: Winthrop Cares wants the Silver sponsor tier, Pacini Tile renewed for 3 years, and Revere Youth Soccer wants a meeting with you personally. Want me to book Soccer first?",
    penelope:  "Events snapshot: 4 live, 182 RSVPs tracked, 81% average show rate. The Wednesday Small Business Office Hours is at 34 RSVPs, up 18% from last month. I've got a one-click reminder sequence ready — send Monday 9am or hold for your final list?",
    sophia:    "Member lifecycle board: 9 new members onboarded, 4 lapsed re-engaged, 2 at renewal risk (auto repair shop and a yoga studio — both late-openers). I've queued Sophia-sequence #3 for both; you'll see the drafts in your approvals tray.",
    iris:      "Newsletter status: April issue at 42% open / 11% click-through, healthy above benchmark. I've got the May draft warming — Board spotlight plus Gala save-the-date plus member business of the month. Want to sign off on the spotlight choice?",
    athena:    "April Board meeting is fully documented — minutes shipped, 12 motions logged, 34 action items tracked with owners. The only overdue item is the Broadway streetscape response memo from Rick. Want me to nudge him?",
    echo:      "Reviews across the member roster: 127 monitored, 14-min average response time, net sentiment +78. Two items need eyes: a 3★ for Joe's Pizza (already drafted, awaiting owner approval) and a 1★ flagged as spam on Kelly's Roast Beef (filed with Google).",
    cleopatra: "Creative board: 68 assets shipped this month, average Lumina score 9.4, brand-consistency 100%. The Gala save-the-date flyer and the May member spotlight hero are ready for your review — rendered on-brand against the Chamber pack. Want the slideshow?",
    aria:      "Aria online. Ready when you are. You can ask me anything — member count, next Board meeting, a quick thank-you draft, a sponsor follow-up. I'll speak the answer and hand the rest to the right specialist. Tap a chip or just say the word."
  };

  // Three scripted follow-ups per agent — cycled on successive messages
  var FOLLOW_UPS = {
    atlas: [
      "Routing: Sophia takes the two at-risk renewals, Artemis gets the sponsor re-engagement list, Athena has the Board memo, Cleopatra is on the Gala flyer. Everything lands in your approvals tray by 4pm. Say the word if you want any item bumped to Sophia directly.",
      "Blocker check — only one: the streetscape response memo is waiting on Rick. Everything else is self-healing. I'll ping Rick through Iris's Friday reminder loop if that's easier than a direct ask.",
      "I can run a dry-rehearsal for Tuesday's Board meeting with Athena — she'll simulate likely questions from the data and pre-brief you on the three items most likely to provoke discussion. Twelve minutes, done from your phone with Aria. Queue it?"
    ],
    hermes: [
      "FAQ draft is live: event calendar, renewal dates, member directory, sponsor contact, bilingual support. I handed it to Cleopatra for a print-ready flyer version too — expect both in your inbox by 2pm.",
      "Two calls this week mentioned payment confusion (Corporate tier 3-year billing). I'll ask Iris to add a Q&A card to the May newsletter clarifying $1,000-for-three-years, effectively $333/yr. Approve?",
      "Ticketing tiers are holding at 73% tier-1 resolution. Top escalations to you: member-onboarding clarifications and Board-contact routing. Both fixable with a public Board roster page — want me to flag that to Athena for the next meeting?"
    ],
    artemis: [
      "Booked — Revere Youth Soccer League, Wednesday 3pm, Zoom. I prepped a briefing doc for you: their ask ($500 jersey patch), our offer (branded jersey + social series on league night), and the pro-bono community-fit angle. It's on your calendar.",
      "Pacini Tile's 3-year renewal paperwork is in the Chamber pack — auto-invoice lined up for the 15th. Nothing for you to do unless they ask for an extension.",
      "Outbound queue for next week: 6 lapsed members (auto-dialed Tuesday 10am), 3 sponsor follow-ups, 2 new-business warm leads from the directory crawl. I'll flag any reply that needs your touch."
    ],
    penelope: [
      "Reminder sequence is live — Monday 9am first touch, Wednesday 8am second, day-of text-nudge. I'll tune it against last-cycle show rates and report a one-liner after the event.",
      "Gala save-the-date goes out next Monday. Cleopatra has the hero ready (board vote captured on 2026-04-10). RSVP landing page will be portal.reverechamber.org/gala — live by Sunday.",
      "Small Business Office Hours is at 34 RSVPs and capacity for 60. I queued one last reminder for Friday 8am. If we hit 50 by Monday I'd recommend moving to the larger Chamber Hall so we don't overcrowd City Hall again."
    ],
    sophia: [
      "Both at-risk renewals get a warm call from Artemis tomorrow and a follow-up email from me 24 hours later. I've seen this pattern convert 7 of 9 times — we catch them before the 30-day auto-lapse.",
      "Onboarding week-1 check-in for Kelly's Roast Beef: everything green. Week-2 I'll pull GBP baseline and member directory completeness. Standard playbook, no exceptions.",
      "Lifecycle dashboard shows 92% 12-month retention — above Chamber benchmark (84%). The two lapses this year both cited life events, not Chamber value. I'm logging that distinction in the renewal rubric."
    ],
    iris: [
      "Locked in: Board spotlight will be Marisa from North Shore Dental (her community-dental-day story is concrete). Gala save-the-date in the top block. Member business of the month I recommend rotating to Kelly's Roast Beef — their 94 GBP score is a tidy proof point.",
      "Drip campaign for new members: Day 1 welcome, Day 7 first-event nudge, Day 30 first-check-in. Open rates 48 / 41 / 37 across the sequence. Want me to add a Day 60 satisfaction survey?",
      "Bilingual send is live for the Spanish portion of the list. Separate subject-line variants tested last issue: Spanish version out-opened English by 6 points. I'll keep that split."
    ],
    athena: [
      "Minutes are filed, tagged, and searchable. I linked every motion to the corresponding action-item owner and set the 30-day status check to auto-fire. Board portal shows current state any time you want it.",
      "Rick has been nudged — he replied he'll ship the memo by Friday 5pm. I'll hold my own action-item timer until 5:01pm and only then escalate.",
      "Dry-rehearsal scheduled with Atlas for Tuesday 9am — 12 minutes, phone-only. I'll pre-brief you on the three highest-friction agenda items plus likely Board questions based on the last six meetings."
    ],
    echo: [
      "Joe's 3★ response is approved and sent. I added the incident to the kitchen-review log and queued the Pioli-family follow-up email for Friday. No further action needed on your side.",
      "Sentiment is stable — Joe's Pizza trending up 0.3★ month-over-month, Kelly's flat, and North Shore Auto Body dipped 0.2★ (two service complaints, both legitimate, both responded to). I'll flag if the dip continues past 2 weeks.",
      "Monthly reputation report for the Board will show: 127 reviews monitored, 14-min average response, zero unhandled negatives. Athena and Iris both want the summary — I'll ship one version each in the formats they need."
    ],
    cleopatra: [
      "Slideshow ready: Gala save-the-date hero, May spotlight banner, Small Business Office Hours flyer, and a Sponsor-of-the-Month template. All scored 9.3+ by Lumina against the Chamber brand pack. Want to see them in the Creative tray or have them auto-routed?",
      "Brand-consistency check ran this morning across 68 assets — 100% inside the Chamber pack. One warning: two old flyers from March used the pre-v4 navy; I've queued re-renders, nothing shipped from them this cycle.",
      "For the Gala, I'd recommend Ideogram for the flyer (legible baked-in text) and Flux for the photorealistic Chamber-Hall hero. Budget is well inside the May cap — Lumina gate stays on, no surprises."
    ],
    aria: [
      "Revere Chamber added 9 new members this month. 4 renewals pending, 2 flagged at-risk. Sophia has both at-risk accounts in a warm-touch sequence starting tomorrow. Want me to text you when the first reply comes in?",
      "Sponsor thank-you drafted: 'Kay — thank you for championing the 2026 Revere Chamber Gala. Your support funds the scholarship, the bilingual outreach, and one more year of connecting our business community. We will see you May 18. — Don Martelli, President.' Send as-is or tweak?",
      "Next Board meeting proposed for Thursday May 7, 6pm at Chamber Hall. I've checked the Board's availability — 9 of 11 free, I've auto-held their calendars. Athena will prep the agenda draft by Monday. Confirm?"
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
