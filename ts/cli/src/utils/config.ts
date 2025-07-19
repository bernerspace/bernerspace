import fs from "fs";
import os from "os";
import path from "path";

const CONFIG_DIR = path.join(os.homedir(), ".benerspace");
const CONFIG_FILE = path.join(CONFIG_DIR, "config.json");

export interface UserConfig {
  token: string;
  email: string;
  username?: string;
  avatar_url?: string;
}
export function saveConfig(config: UserConfig) {
  if (!fs.existsSync(CONFIG_DIR)) {
    fs.mkdirSync(CONFIG_DIR, { recursive: true });
  }
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

export function loadConfig(): UserConfig {
  if (!fs.existsSync(CONFIG_FILE)) {
    throw new Error("ConfigNotInitialized");
  }
  return JSON.parse(fs.readFileSync(CONFIG_FILE, "utf-8"));
}
