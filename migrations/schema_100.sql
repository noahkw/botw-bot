-- This script copies data from the schema 'bootstrap' to the schema 'public'.
-- Create the bootstrap schema by renaming the public schema, then create a new public schema.
-- The public schema and its tables/types need to be created by SQLALchemy beforehand.


-- tags
INSERT INTO public.tags (tag_id, trigger, reaction, in_msg, _creator, _guild, use_count, date)
SELECT id, trigger, reaction, in_msg, creator, guild, use_count, date FROM bootstrap.tags;

-- roles
INSERT INTO public.roles (_role, _guild, clear_after, enabled)
SELECT "role", guild, clear_after, active FROM bootstrap.roles;

INSERT INTO public.role_aliases (_role, _guild, alias)
SELECT "role", guild, alias FROM bootstrap.role_aliases;

-- skip role clears, not needed

-- reminders
INSERT INTO public.reminders (reminder_id, _user, due, created, done, "content")
SELECT "id", "user", due, created, done, "content" FROM bootstrap.reminders;

-- profiles
INSERT INTO public.profiles (_user, "location")
SELECT  "user", "location" FROM bootstrap.profiles;

-- skip idols, not needed

-- guild_settings
INSERT INTO public.guild_settings (_guild, prefix)
SELECT guild, prefix FROM bootstrap.prefixes;

-- greeters
INSERT INTO public.greeters (_guild, _channel, template, type)
SELECT guild, channel, template,
       CASE
           WHEN type = 'join'
               THEN 'JOIN'::public.greetertype
           ELSE 'LEAVE'::public.greetertype
       END
FROM bootstrap.greeters;

-- emoji_settings
INSERT INTO public.emoji_settings (_guild, _channel)
SELECT guild, emoji_channel FROM bootstrap.emoji_settings;

-- channel_mirrors
INSERT INTO public.channel_mirrors (_origin, _destination, _webhook, enabled)
SELECT origin, destination, webhook, enabled FROM bootstrap.mirrors;

-- botw_winners
INSERT INTO public.botw_winners (_botw_winner, idol_group, idol_name, _guild, _member, date)
SELECT "id", idol_group, idol_name, guild, member, date FROM bootstrap.botw_winners;

-- botw_settings
INSERT INTO public.botw_settings (_guild, _botw_channel, _nominations_channel, enabled, winner_changes, state)
SELECT guild, botw_channel, nominations_channel, enabled, winner_changes,
       CASE
           WHEN state = 'DEFAULT'
               THEN 'DEFAULT'::public.botwstate
           WHEN state = 'WINNER_CHOSEN'
               THEN 'WINNER_CHOSEN'::public.botwstate
           WHEN state = 'SKIP'
               THEN 'SKIP'::public.botwstate
           ELSE 'DEFAULT'::public.botwstate
       END
FROM bootstrap.botw_settings;

-- botw_nominations
INSERT INTO public.botw_nominations (idol_group, idol_name, _guild, _member)
SELECT idol_group, idol_name, guild, member FROM bootstrap.botw_nominations;

CREATE EXTENSION pg_trgm;
