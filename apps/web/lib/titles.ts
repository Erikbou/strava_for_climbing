/** Random title pool — mirrors strava_climbing.titles for parity with the
 *  Streamlit upload flow's "random" mode. Kept small/punchy. */
const POOL: string[] = [
  "Wednesday Project",
  "Crimp Crusader",
  "Heel Hook Heaven",
  "Slab Whisperer",
  "Dyno Disaster",
  "Compression Crisis",
  "Crux Conqueror",
  "Sloper Saga",
  "Toe Hook Tango",
  "Flagging Frenzy",
  "Mantle Mayhem",
  "Beta Breakdown",
  "Send Train",
  "Flash Dance",
  "Powder Pinch",
  "Static Standoff",
  "Coordination Crisis",
  "Lockoff Legend",
  "Drop Knee Drama",
  "Bumper Plate",
];

export function randomTitle(): string {
  return POOL[Math.floor(Math.random() * POOL.length)];
}
