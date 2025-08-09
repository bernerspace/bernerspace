
# Slack MCP Tools Reference

Bernerspace MCP supports over 47 Slack tools for authentication, messaging, channels, users, files, reactions, history, pins, bookmarks, usergroups, team info, emoji, and do-not-disturb features. Below is a comprehensive reference for all available endpoints and capabilities.

## Authentication & Testing

- **test_slack_auth** - Verify bot authentication credentials and retrieve workspace connection details

## Messaging Tools

- **send_slack_message** - Send messages to channels or users with support for rich formatting, blocks, attachments, and threading
- **update_slack_message** - Modify existing messages with new content, formatting, or attachments
- **delete_slack_message** - Remove messages from channels permanently
- **schedule_slack_message** - Queue messages to be automatically sent at specified future times

## Channel Tools

- **list_slack_channels** - Browse and discover available channels in the workspace with filtering options
- **get_slack_channel_info** - Retrieve comprehensive channel details including members, settings, and metadata
- **create_slack_channel** - Establish new public or private channels for team communication
- **join_slack_channel** - Connect the bot to existing channels for participation
- **leave_slack_channel** - Remove the bot from channels when no longer needed
- **invite_to_slack_channel** - Add team members to channels for collaboration
- **kick_from_slack_channel** - Remove users from channels for moderation purposes
- **set_slack_channel_topic** - Update channel topics to reflect current discussion themes
- **set_slack_channel_purpose** - Define and modify the intended use case for channels
- **archive_slack_channel** - Preserve channel history while making it read-only
- **unarchive_slack_channel** - Restore archived channels to active status

## User Tools

- **list_slack_users** - Enumerate workspace members with pagination and filtering capabilities
- **get_slack_user_info** - Access detailed user profiles including roles, status, and contact information
- **get_slack_user_profile** - Retrieve specific profile fields and custom attributes for users
- **set_slack_presence** - Control bot availability status and online presence indicators

## File Tools

- **upload_slack_file** - Share files from various sources including URLs, local storage, or text content
- **list_slack_files** - Browse uploaded files with filtering by channel, user, date, and file type
- **get_slack_file_info** - Access file metadata, permissions, and sharing details
- **delete_slack_file** - Remove files from workspace storage permanently

## Reaction Tools

- **add_slack_reaction** - Express sentiment or acknowledgment using emoji reactions on messages
- **remove_slack_reaction** - Withdraw previously added emoji reactions from messages
- **get_slack_reactions** - View all reactions and their contributors for specific messages

## History & Information Tools

- **get_slack_channel_history** - Retrieve past messages and conversations from channels with time-based filtering
- **get_slack_thread_replies** - Access complete threaded conversations and reply chains

## Pin Tools

- **pin_slack_message** - Highlight important messages for easy reference by all channel members
- **unpin_slack_message** - Remove messages from the pinned items collection
- **list_slack_pins** - View all currently pinned items and files in a channel

## Bookmark Tools

- **add_slack_bookmark** - Create quick-access links and resources for channel members
- **remove_slack_bookmark** - Delete bookmarks that are no longer relevant or needed
- **list_slack_bookmarks** - Browse all saved bookmarks and resources in a channel

## Usergroup Tools

- **create_slack_usergroup** - Establish team groups for mentions, permissions, and organization
- **list_slack_usergroups** - View all existing user groups and their current status
- **update_slack_usergroup** - Modify group names, descriptions, and member lists
- **disable_slack_usergroup** - Deactivate user groups while preserving their configuration

## Team Tools

- **get_slack_team_info** - Access workspace-level information including settings, features, and limits
- **get_slack_team_profile** - Retrieve organization profile fields and custom workspace attributes

## Emoji Tools

- **list_slack_emoji** - Browse custom emoji available in the workspace for reactions and messages

## Do Not Disturb Tools

- **get_slack_dnd_info** - Check user availability and notification preferences to respect focus time
- **get_slack_team_dnd_info** - Monitor team-wide do-not-disturb status for multiple users simultaneously
