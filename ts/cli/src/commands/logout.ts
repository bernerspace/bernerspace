// src/commands/logout.ts
import { Command } from "commander";
import fs from "fs";
import { CONFIG_FILE } from "../utils/config";

const logout = new Command("logout")
  .description("Remove saved token and email from config")
  .action(() => {
    fs.rmSync(CONFIG_FILE, { force: true });
    console.log("Logged out; credentials removed.");
  });

export default logout;
