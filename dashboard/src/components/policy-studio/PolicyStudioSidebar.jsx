/**
 * Right rail: HelpCard, ExampleCard, LiveSummaryCard. Content changes by step; summary reflects current draft.
 */
import HelpCard from './sidebar/HelpCard';
import ExampleCard from './sidebar/ExampleCard';
import LiveSummaryCard from './sidebar/LiveSummaryCard';

const HELP = {
  basics: {
    title: 'Help',
    body: 'Give your policy a clear name and describe what it does. Outcome determines what happens when the policy matches (Detect, Warn, Require approval, or Block).',
  },
  source: {
    title: 'Where should this policy look?',
    body: 'Choose the data source this policy applies to. Endpoint-native sources are available now; more connectors may be added later.',
  },
  scope: {
    title: 'What to protect or govern',
    body: 'Select the types of data or activity this policy should consider. Your selections are combined with the source and rules to form the full policy.',
  },
  rules: {
    title: 'Conditions and action',
    body: 'Simple mode builds conditions from your Basics and Scope. Use Advanced mode to edit the full condition structure (confidence bands, tool classes, etc.).',
  },
  review: {
    title: 'Review',
    body: 'Review your policy before saving or publishing. Save as draft to continue later, or publish to activate the policy.',
  },
};

const EXAMPLES = {
  basics: { title: 'Example', body: 'e.g. "Block high-risk tools on sensitive paths" with outcome "Block" and severity "High".' },
  source: { title: 'Tip', body: 'Select "Local agent / IDE & CLI" to govern tools like Cursor and Copilot on endpoints.' },
  scope: { title: 'Tip', body: 'Select "Source code" and "Credentials" to protect repos and secrets.' },
  rules: { title: 'Tip', body: 'Start with Simple mode; switch to Advanced only if you need custom conditions.' },
  review: { title: '', body: '' },
};

export default function PolicyStudioSidebar({ stepId, draft }) {
  const help = HELP[stepId] || HELP.basics;
  const example = EXAMPLES[stepId];

  return (
    <div className="space-y-4">
      <HelpCard title={help.title} body={help.body} />
      {example?.body && <ExampleCard title={example.title} body={example.body} />}
      <LiveSummaryCard draft={draft} />
    </div>
  );
}
