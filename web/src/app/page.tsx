import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Header } from "@/components/shell";

const steps = [
  {
    eyebrow: "01 · READ",
    title: "The file stays here",
    body: "Spreadsheets, contracts, exports. Parsed on the machine you are sitting at, never uploaded to a vendor.",
  },
  {
    eyebrow: "02 · DECIDE",
    title: "A local model reads it first",
    body: "Qwen runs on the Dell GB10 and marks what has to go: names, account numbers, exact amounts, anything that identifies a person.",
  },
  {
    eyebrow: "03 · RETURN",
    title: "You get a safe copy",
    body: "Same document, same structure, same format. Names become handles, amounts become bands. Download it and use whatever tool you like.",
  },
];

export default function Home() {
  return (
    <>
      <section className="relative isolate overflow-hidden">
        <div className="sky" aria-hidden />
        <div className="relative">
          <Header
            tagline="LOCAL REDACTION · DELL GB10"
            action={
              <Button asChild variant="ghost" size="sm">
                <Link href="/desk">Open the desk</Link>
              </Button>
            }
          />
          <div className="mx-auto w-full max-w-[1240px] px-6 pt-16 pb-40 md:px-12 md:pt-24 md:pb-56">
            <div className="max-w-[760px]">
              <p className="text-[13px] font-semibold tracking-[-0.01em] text-accent-dark">
                Use the good tools on the difficult documents
              </p>
              <h1 className="mt-4 text-[40px] leading-[1.05] font-semibold tracking-[-0.035em] sm:text-[56px]">
                Drop a document.
                <br />
                Get a safe one back.
              </h1>
              <p className="mt-6 max-w-[52ch] text-[17px] text-ink-2">
                Your report is due tomorrow and the file is full of client
                names, account numbers and exact figures. SafeContext strips
                those on the box and hands you a copy you are allowed to share.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <Button asChild size="lg">
                  <Link href="/desk">Drop a document</Link>
                </Button>
                <span className="mono-micro">
                  CSV · XLSX · PDF · DOCX · JSON · TXT · MD
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-[1240px] px-6 pb-24 md:px-12">
        <div className="grid gap-4 md:grid-cols-3">
          {steps.map((step) => (
            <div key={step.eyebrow} className="glass rounded-[14px] p-6">
              <p className="mono-eyebrow">{step.eyebrow}</p>
              <h2 className="mt-3 text-[17px] font-semibold tracking-[-0.02em]">
                {step.title}
              </h2>
              <p className="mt-2 text-[14px] text-muted">{step.body}</p>
            </div>
          ))}
        </div>

        <div className="mt-14 border-t border-line pt-8">
          <p className="max-w-[62ch] text-[15px] text-ink-2">
            The model that reads your file runs on the Dell GB10 in the room.
            Nothing is sent to Anthropic, OpenAI or anyone else. What you do
            with the safe copy afterwards is your call.
          </p>
          <p className="mono-micro mt-4">
            SAFECONTEXT · DELL HACKATHON · LOCAL AGENTS
          </p>
        </div>
      </section>
    </>
  );
}
