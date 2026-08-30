import type { ContentPackage, SocialPackage } from "@/lib/types";
import { humanize } from "@/lib/utils";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-zinc-200 py-2.5 last:border-b-0">
      <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">{title}</h4>
      {children}
    </div>
  );
}

function Items({ items, ordered }: { items: unknown; ordered?: boolean }) {
  const list = Array.isArray(items) ? items : items ? [items] : [];
  if (list.length === 0) return <p className="text-xs text-zinc-400">None.</p>;
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag className={`${ordered ? "list-decimal" : "list-disc"} space-y-0.5 pl-4 text-[13px] text-zinc-800`}>
      {list.map((it, i) => (
        <li key={i} className="whitespace-pre-wrap">
          {typeof it === "string" ? it : typeof it === "object" && it !== null ? renderObject(it as Record<string, unknown>) : String(it)}
        </li>
      ))}
    </Tag>
  );
}

function renderObject(o: Record<string, unknown>): React.ReactNode {
  const text = (o.text ?? o.title ?? o.content ?? o.idea ?? o.concept) as string | undefined;
  if (text) {
    const rest = Object.entries(o).filter(([k]) => !["text", "title", "content", "idea", "concept"].includes(k));
    return (
      <span>
        {text}
        {rest.length ? <span className="ml-1 text-xs text-zinc-500">({rest.map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join(", ")})</span> : null}
      </span>
    );
  }
  return <code className="text-xs">{JSON.stringify(o)}</code>;
}

function Text({ value }: { value: unknown }) {
  if (!value) return <p className="text-xs text-zinc-400">Empty.</p>;
  return <p className="whitespace-pre-wrap text-[13px] text-zinc-800">{typeof value === "string" ? value : JSON.stringify(value)}</p>;
}

export function SocialView({ social }: { social: SocialPackage }) {
  const known = ["posts", "thread", "quote_cards", "short_video_ideas", "hooks", "titles", "thumbnail_text", "meme_concepts"];
  return (
    <div>
      {social.posts ? (
        <Block title="Posts">
          <Items items={social.posts} />
        </Block>
      ) : null}
      {social.thread ? (
        <Block title="Thread">
          <Items items={social.thread} ordered />
        </Block>
      ) : null}
      {social.quote_cards ? (
        <Block title="Quote cards">
          <Items items={social.quote_cards} />
        </Block>
      ) : null}
      {social.short_video_ideas ? (
        <Block title="Short video ideas">
          <Items items={social.short_video_ideas} />
        </Block>
      ) : null}
      {social.hooks ? (
        <Block title="Hooks">
          <Items items={social.hooks} ordered />
        </Block>
      ) : null}
      {social.titles ? (
        <Block title="Titles">
          <Items items={social.titles} ordered />
        </Block>
      ) : null}
      {social.thumbnail_text ? (
        <Block title="Thumbnail text">
          <Items items={social.thumbnail_text} />
        </Block>
      ) : null}
      {social.meme_concepts ? (
        <Block title="Meme concepts">
          <Items items={social.meme_concepts} />
        </Block>
      ) : null}
      {Object.entries(social)
        .filter(([k]) => !known.includes(k))
        .map(([k, v]) => (
          <Block key={k} title={humanize(k)}>
            {Array.isArray(v) ? <Items items={v} /> : <Text value={v} />}
          </Block>
        ))}
    </div>
  );
}

const LONG_KEYS = ["working_title", "alternative_titles", "hook", "opening_30s", "thesis", "outline", "research_needed", "arguments", "counterarguments", "examples", "evidence", "transitions", "conclusion", "call_to_discussion", "show_notes", "sources", "social"];

export function PackageView({ pkg }: { pkg: ContentPackage }) {
  const keys = Object.keys(pkg ?? {});
  if (keys.length === 0) return <p className="text-xs text-zinc-400">No structured package. Generate content or add a script.</p>;
  const isLong = LONG_KEYS.some((k) => k in pkg && k !== "social");
  const extra = keys.filter((k) => !LONG_KEYS.includes(k));
  return (
    <div>
      {isLong ? (
        <>
          {(pkg.working_title || pkg.alternative_titles) && (
            <Block title="Titles">
              {pkg.working_title ? <p className="text-[14px] font-semibold text-zinc-900">{pkg.working_title}</p> : null}
              <Items items={pkg.alternative_titles} />
            </Block>
          )}
          {"hook" in pkg ? (
            <Block title="Hook">
              <Text value={pkg.hook} />
            </Block>
          ) : null}
          {"opening_30s" in pkg ? (
            <Block title="Opening (first 30 seconds)">
              <Text value={pkg.opening_30s} />
            </Block>
          ) : null}
          {"thesis" in pkg ? (
            <Block title="Thesis">
              <Text value={pkg.thesis} />
            </Block>
          ) : null}
          {pkg.outline ? (
            <Block title="Outline">
              <ol className="space-y-1.5">
                {pkg.outline.map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="w-5 shrink-0 text-right font-mono text-[11px] text-zinc-400">{i + 1}</span>
                    <div>
                      <div className="text-[13px] font-semibold text-zinc-900">{s.section}</div>
                      {s.notes ? <p className="whitespace-pre-wrap text-[13px] text-zinc-700">{s.notes}</p> : null}
                    </div>
                  </li>
                ))}
              </ol>
            </Block>
          ) : null}
          {pkg.research_needed ? (
            <Block title="Research needed">
              <Items items={pkg.research_needed} />
            </Block>
          ) : null}
          {pkg.arguments ? (
            <Block title="Arguments">
              <Items items={pkg.arguments} />
            </Block>
          ) : null}
          {pkg.counterarguments ? (
            <Block title="Counterarguments">
              <Items items={pkg.counterarguments} />
            </Block>
          ) : null}
          {pkg.examples ? (
            <Block title="Examples">
              <Items items={pkg.examples} />
            </Block>
          ) : null}
          {pkg.evidence ? (
            <Block title="Evidence">
              <Items items={pkg.evidence} />
            </Block>
          ) : null}
          {pkg.transitions ? (
            <Block title="Transitions">
              <Items items={pkg.transitions} />
            </Block>
          ) : null}
          {"conclusion" in pkg ? (
            <Block title="Conclusion">
              <Text value={pkg.conclusion} />
            </Block>
          ) : null}
          {"call_to_discussion" in pkg ? (
            <Block title="Call to discussion">
              <Text value={pkg.call_to_discussion} />
            </Block>
          ) : null}
          {"show_notes" in pkg ? (
            <Block title="Show notes">
              <Text value={pkg.show_notes} />
            </Block>
          ) : null}
          {pkg.sources ? (
            <Block title="Sources">
              <ul className="list-disc space-y-0.5 pl-4 text-[13px]">
                {pkg.sources.map((s, i) => (
                  <li key={i}>
                    {/^https?:\/\//.test(s) ? (
                      <a href={s} target="_blank" rel="noreferrer" className="break-all text-accent-strong hover:underline">
                        {s}
                      </a>
                    ) : (
                      s
                    )}
                  </li>
                ))}
              </ul>
            </Block>
          ) : null}
        </>
      ) : null}
      {pkg.social ? (
        <Block title="Social derivatives">
          <SocialView social={pkg.social} />
        </Block>
      ) : null}
      {extra.map((k) => (
        <Block key={k} title={humanize(k)}>
          {Array.isArray(pkg[k]) ? <Items items={pkg[k]} /> : typeof pkg[k] === "object" && pkg[k] !== null ? <pre className="overflow-auto rounded bg-zinc-50 p-2 font-mono text-[11px]">{JSON.stringify(pkg[k], null, 2)}</pre> : <Text value={pkg[k]} />}
        </Block>
      ))}
    </div>
  );
}
