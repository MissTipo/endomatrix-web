import { detectPatterns } from "../engine/patternEngine";

test("detects symptom patterns from logs", () => {
  const logs = [
    { date: "2026-01-01", painScore: 8, energyScore: 3, dominantSymptom: "pelvic_pain" },
    { date: "2026-01-02", painScore: 6, energyScore: 4, dominantSymptom: "pelvic_pain" },
    { date: "2026-01-03", painScore: 4, energyScore: 6, dominantSymptom: "acne" },
  ];

  const patterns = detectPatterns(logs);

  expect(patterns.length).toBe(2);
});

