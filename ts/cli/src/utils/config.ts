import fs from "fs";
import os from "os";
import path from "path";

const CONFIG_DIR = path.join(os.homedir(), ".bernerspace");
const CONFIG_FILE = path.join(CONFIG_DIR, "config.json");

export function saveConfig(token: string, email: string) {
  if (!fs.existsSync(CONFIG_DIR)) fs.mkdirSync(CONFIG_DIR, { recursive: true });
  fs.writeFileSync(CONFIG_FILE, JSON.stringify({ token, email }, null, 2));
}

export function loadConfig(): { token: string; email: string } {
  if (!fs.existsSync(CONFIG_FILE)) {
    throw new Error("ConfigNotInitialized");
  }
  return JSON.parse(fs.readFileSync(CONFIG_FILE, "utf-8"));
}
