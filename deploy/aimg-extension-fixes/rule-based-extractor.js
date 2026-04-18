/**
 * Rule-Based Memory Extractor
 * Extracts facts, decisions, preferences, and corrections from AI responses
 * WITHOUT requiring an LLM call. Used for Free tier (zero API cost).
 * Pro tier adds server-side LLM extraction for higher quality.
 */

const EXTRACTION_RULES = {
  decisions: [
    /(?:I(?:'ve|'ll| will| have))?\s*(?:decided?|chosen?|going with|settled on|committed to|picked)\s+(.{10,150})/gi,
    /(?:the decision is|we(?:'re| are) going with|final (?:answer|call|choice)[:\s]+)(.{10,150})/gi,
    /(?:let(?:'s| us) go with|I(?:'m| am) going to)\s+(.{10,150})/gi
  ],
  facts: [
    /(?:I (?:am|work|live|use|prefer|like|have|own|manage|run|built|created|started))\s+(.{10,150})/gi,
    /(?:my (?:name|job|role|company|team|project|tool|stack|preference|favorite|goal) is)\s+(.{10,150})/gi,
    /(?:we use|our (?:stack|tool|platform|process|workflow) is)\s+(.{10,150})/gi
  ],
  corrections: [
    /(?:actually|correction|no,? that(?:'s| is) wrong|I was wrong|update:?|changed? (?:my mind|this))\s+(.{10,200})/gi,
    /(?:it(?:'s| is) (?:actually|now)|not .{5,50} but rather)\s+(.{10,150})/gi,
    /(?:scratch that|forget what I said|disregard|instead,?)\s+(.{10,150})/gi
  ],
  actions: [
    /(?:TODO|TASK|ACTION|next step|I need to|don't forget to|remind me to|make sure to)\s*:?\s*(.{10,150})/gi,
    /(?:the plan is to|we(?:'re| are) going to|next we(?:'ll| will))\s+(.{10,150})/gi
  ]
};

function extractMemories(text, provenance) {
  const memories = [];
  const seen = new Set();

  for (const [type, patterns] of Object.entries(EXTRACTION_RULES)) {
    for (const pattern of patterns) {
      pattern.lastIndex = 0;
      let match;

      while ((match = pattern.exec(text)) !== null) {
        const extracted = match[1]?.trim();
        if (!extracted || extracted.length < 10) continue;

        const key = extracted.substring(0, 50).toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);

        const cleaned = cleanExtraction(extracted);
        if (!cleaned) continue;

        memories.push({
          type: type === 'decisions' ? 'decision' :
                type === 'facts' ? 'fact' :
                type === 'corrections' ? 'correction' :
                'action',
          content: cleaned,
          confidence: calculateConfidence(type, cleaned),
          provenance: { ...provenance },
          extracted_at: new Date().toISOString()
        });
      }
    }
  }

  return memories;
}

function cleanExtraction(text) {
  let cleaned = text.replace(/[,;:]\s*$/, '').trim();
  cleaned = cleaned.replace(/^(?:and|but|or|so|then)\s+/i, '');
  if (cleaned.length > 150) {
    const sentenceEnd = cleaned.indexOf('. ');
    if (sentenceEnd > 30) cleaned = cleaned.substring(0, sentenceEnd + 1);
  }
  return cleaned.length >= 10 ? cleaned : null;
}

function calculateConfidence(type, text) {
  let confidence = 0.6;
  if (type === 'corrections') confidence = 0.9;
  if (type === 'decisions' && /final|definitely|committed/i.test(text)) confidence = 0.85;
  if (type === 'facts' && text.length < 60) confidence = 0.75;
  if (/maybe|might|possibly|not sure|I think/i.test(text)) confidence *= 0.7;
  return Math.round(confidence * 100) / 100;
}

function detectContradictions(newMemory, existingMemories) {
  const contradictions = [];
  const newTokens = tokenize(newMemory.content);

  for (const existing of existingMemories) {
    if (existing.type !== newMemory.type) continue;
    
    const existingTokens = tokenize(existing.content);
    const overlap = newTokens.filter(t => existingTokens.includes(t));
    
    if (overlap.length >= 3) {
      const similarity = overlap.length / Math.max(newTokens.length, existingTokens.length);
      if (similarity > 0.3 && similarity < 0.9) {
        contradictions.push({
          existing_memory_id: existing.id,
          existing_content: existing.content,
          new_content: newMemory.content,
          overlap_score: similarity,
          action: newMemory.type === 'correction' ? 'supersede' : 'flag_for_review'
        });
      }
    }
  }

  return contradictions;
}

function tokenize(text) {
  return text.toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .split(/\s+/)
    .filter(t => t.length > 3);
}

if (typeof module !== 'undefined') {
  module.exports = { extractMemories, detectContradictions };
}
