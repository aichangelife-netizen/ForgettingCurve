# Manual MVP Test

This scenario uses short development intervals. It does not fake production UI timestamps.

1. Import demonstration vocabulary:

   ```sh
   cd backend
   uv run python scripts/import_vocabulary.py
   ```

2. Start the backend:

   ```sh
   cd backend
   uv run uvicorn app.main:app --reload
   ```

3. Start the frontend:

   ```sh
   cd frontend
   npm run dev
   ```

4. Open `http://localhost:3000`.

5. Select `Create New Participant`.

6. On `/experiment`, select `Create New Experiment`.

7. On `/experiment/design`, choose the Development preset:

   ```text
   60, 180, 300, 600, 1200
   ```

8. Confirm the required item count, create the draft design, note the stored random seed, and select `Start Learning`.

9. On the learning page, review study materials, then begin learning checks.

10. Answer each Korean prompt until every vocabulary item is mastered with two consecutive correct answers.

11. Select `Initialize Test Groups`.

12. On activation review, review each Korean-English pair and select `I Have Reviewed This Word`. Each click creates that word's scheduling anchor.

13. Open the delayed-test page. If no test is due, inspect the next scheduled time and wait.

14. Submit delayed recalls as they become due. During active delayed testing, the UI shows no correctness and no canonical English answer.

15. Open results while the experiment is partial to inspect raw summaries. No provisional curve is shown below five complete time points.

16. Finish all delayed-recall groups.

17. On results, inspect raw group summaries first.

18. Select `Generate Personal Curve` when the backend reports eligibility.

19. Inspect Personal Curve V1, including observed point markers, fitted predicted line, T, c, sample count, complete time point count, warnings, and fitted timestamp.

20. After later completed experiments, return to results and use curve-version history to inspect historical versions. Older versions are not edited or refitted.
