import { Command } from "commander";
import initCommand from "./commands/init";
import logoutCommand from "./commands/logout";
import detailsCommand from "./commands/details";

const program = new Command();
program
  .name("bernerspace")
  .description("CLI for Bernerspace project management")
  .version("0.1.0");

program.addCommand(initCommand);
program.addCommand(logoutCommand);
program.addCommand(detailsCommand);

program.parse(process.argv);
