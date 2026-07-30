"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { createParticipant } from "@/lib/api/participants";
import { clearParticipantSession, readParticipantSession, saveParticipantSession } from "@/lib/participant-session";

export default function Home() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  async function handleCreate() {
    setIsCreating(true);
    setMessage(null);
    try {
      const participant = await createParticipant();
      saveParticipantSession({ participantId: participant.id, participantCode: participant.participant_code });
      router.push("/experiment");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create a participant.");
    } finally {
      setIsCreating(false);
    }
  }

  function handleResume() {
    const session = readParticipantSession();
    if (!session) {
      clearParticipantSession();
      setMessage("The participant session could not be found.");
      return;
    }
    router.push("/experiment");
  }

  return (
    <main className="landing">
      <section className="hero">
        <p className="eyebrow">Local research MVP</p>
        <h1>Korean-to-English vocabulary memory experiment</h1>
        <p className="lede">
          You will first study vocabulary, then answer each word correctly twice in succession. Later tests occur at
          intervals you choose, and after enough completed time points the system estimates an official personal
          forgetting curve.
        </p>
        <div className="info-grid" aria-label="Experiment basics">
          <div>
            <h2>Study First</h2>
            <p>Review Korean prompts and canonical English answers before checks begin.</p>
          </div>
          <div>
            <h2>Exact Matching</h2>
            <p>Learning and delayed tests use exact English-answer matching.</p>
          </div>
          <div>
            <h2>Delayed Recall</h2>
            <p>Each reviewed word receives its own memory-time anchor for future tests.</p>
          </div>
        </div>
        <div className="button-row">
          <button type="button" onClick={handleCreate} disabled={isCreating}>
            {isCreating ? "Creating..." : "Create New Participant"}
          </button>
          <button type="button" className="secondary-button" onClick={handleResume}>
            Resume Current Experiment
          </button>
          <Link className="secondary-button" href="/experiment/design">
            Create Design
          </Link>
        </div>
        {message ? (
          <p className="status-text" role="status">
            {message}
          </p>
        ) : null}
      </section>
    </main>
  );
}
