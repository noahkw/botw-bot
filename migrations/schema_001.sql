--
-- PostgreSQL database dump
--

-- Dumped from database version 12.3 (Debian 12.3-1.pgdg100+1)
-- Dumped by pg_dump version 12.3

-- Started on 2020-08-12 16:12:29

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 2 (class 3079 OID 65538)
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- TOC entry 3037 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- TOC entry 583 (class 1247 OID 65616)
-- Name: botw_state_type; Type: TYPE; Schema: public; Owner: botw-bot
--

CREATE TYPE public.botw_state_type AS ENUM (
    'DEFAULT',
    'WINNER_CHOSEN',
    'SKIP'
);


ALTER TYPE public.botw_state_type OWNER TO "botw-bot";

--
-- TOC entry 671 (class 1247 OID 65624)
-- Name: greeter_type; Type: TYPE; Schema: public; Owner: botw-bot
--

CREATE TYPE public.greeter_type AS ENUM (
    'join',
    'leave'
);


ALTER TYPE public.greeter_type OWNER TO "botw-bot";

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 203 (class 1259 OID 65629)
-- Name: botw_nominations; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.botw_nominations (
    guild bigint NOT NULL,
    idol_group character varying(255) NOT NULL,
    idol_name character varying(255) NOT NULL,
    member bigint NOT NULL
);


ALTER TABLE public.botw_nominations OWNER TO "botw-bot";

--
-- TOC entry 204 (class 1259 OID 65635)
-- Name: botw_settings; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.botw_settings (
    botw_channel bigint NOT NULL,
    enabled boolean NOT NULL,
    nominations_channel bigint NOT NULL,
    state public.botw_state_type NOT NULL,
    winner_changes boolean NOT NULL,
    guild bigint NOT NULL
);


ALTER TABLE public.botw_settings OWNER TO "botw-bot";

--
-- TOC entry 205 (class 1259 OID 65638)
-- Name: botw_winners; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.botw_winners (
    id integer NOT NULL,
    guild bigint NOT NULL,
    date timestamp with time zone NOT NULL,
    idol_group character varying(255) NOT NULL,
    idol_name character varying(255) NOT NULL,
    member bigint NOT NULL
);


ALTER TABLE public.botw_winners OWNER TO "botw-bot";

--
-- TOC entry 206 (class 1259 OID 65644)
-- Name: botw_winners_id_seq; Type: SEQUENCE; Schema: public; Owner: botw-bot
--

CREATE SEQUENCE public.botw_winners_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.botw_winners_id_seq OWNER TO "botw-bot";

--
-- TOC entry 3038 (class 0 OID 0)
-- Dependencies: 206
-- Name: botw_winners_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: botw-bot
--

ALTER SEQUENCE public.botw_winners_id_seq OWNED BY public.botw_winners.id;


--
-- TOC entry 207 (class 1259 OID 65646)
-- Name: emoji_settings; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.emoji_settings (
    guild bigint NOT NULL,
    emoji_channel bigint
);


ALTER TABLE public.emoji_settings OWNER TO "botw-bot";

--
-- TOC entry 208 (class 1259 OID 65649)
-- Name: greeters; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.greeters (
    channel bigint NOT NULL,
    guild bigint NOT NULL,
    template text,
    type public.greeter_type NOT NULL
);


ALTER TABLE public.greeters OWNER TO "botw-bot";

--
-- TOC entry 209 (class 1259 OID 65655)
-- Name: idols; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.idols (
    "group" character varying(255) NOT NULL,
    name character varying(255) NOT NULL
);


ALTER TABLE public.idols OWNER TO "botw-bot";

--
-- TOC entry 210 (class 1259 OID 65661)
-- Name: mirrors; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.mirrors (
    destination bigint NOT NULL,
    enabled boolean NOT NULL,
    origin bigint NOT NULL,
    webhook bigint NOT NULL
);


ALTER TABLE public.mirrors OWNER TO "botw-bot";

--
-- TOC entry 211 (class 1259 OID 65664)
-- Name: prefixes; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.prefixes (
    guild bigint NOT NULL,
    prefix character varying(10)
);


ALTER TABLE public.prefixes OWNER TO "botw-bot";

--
-- TOC entry 212 (class 1259 OID 65667)
-- Name: profiles; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.profiles (
    "user" bigint NOT NULL,
    location character varying(255)
);


ALTER TABLE public.profiles OWNER TO "botw-bot";

--
-- TOC entry 213 (class 1259 OID 65670)
-- Name: reminders; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.reminders (
    id integer NOT NULL,
    content text NOT NULL,
    created timestamp with time zone NOT NULL,
    done boolean NOT NULL,
    due timestamp with time zone NOT NULL,
    "user" bigint NOT NULL
);


ALTER TABLE public.reminders OWNER TO "botw-bot";

--
-- TOC entry 214 (class 1259 OID 65676)
-- Name: reminders_id_seq; Type: SEQUENCE; Schema: public; Owner: botw-bot
--

CREATE SEQUENCE public.reminders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.reminders_id_seq OWNER TO "botw-bot";

--
-- TOC entry 3039 (class 0 OID 0)
-- Dependencies: 214
-- Name: reminders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: botw-bot
--

ALTER SEQUENCE public.reminders_id_seq OWNED BY public.reminders.id;


--
-- TOC entry 215 (class 1259 OID 65678)
-- Name: tags; Type: TABLE; Schema: public; Owner: botw-bot
--

CREATE TABLE public.tags (
    id integer NOT NULL,
    date timestamp with time zone NOT NULL,
    creator bigint NOT NULL,
    guild bigint NOT NULL,
    in_msg boolean NOT NULL,
    reaction text NOT NULL,
    trigger text NOT NULL,
    use_count integer NOT NULL
);


ALTER TABLE public.tags OWNER TO "botw-bot";

--
-- TOC entry 216 (class 1259 OID 65684)
-- Name: tags_id_seq; Type: SEQUENCE; Schema: public; Owner: botw-bot
--

CREATE SEQUENCE public.tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.tags_id_seq OWNER TO "botw-bot";

--
-- TOC entry 3040 (class 0 OID 0)
-- Dependencies: 216
-- Name: tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: botw-bot
--

ALTER SEQUENCE public.tags_id_seq OWNED BY public.tags.id;


--
-- TOC entry 2881 (class 2604 OID 65686)
-- Name: botw_winners id; Type: DEFAULT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.botw_winners ALTER COLUMN id SET DEFAULT nextval('public.botw_winners_id_seq'::regclass);


--
-- TOC entry 2882 (class 2604 OID 65687)
-- Name: reminders id; Type: DEFAULT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.reminders ALTER COLUMN id SET DEFAULT nextval('public.reminders_id_seq'::regclass);


--
-- TOC entry 2883 (class 2604 OID 65688)
-- Name: tags id; Type: DEFAULT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.tags ALTER COLUMN id SET DEFAULT nextval('public.tags_id_seq'::regclass);


--
-- TOC entry 2885 (class 2606 OID 65690)
-- Name: botw_nominations botw_nominations_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.botw_nominations
    ADD CONSTRAINT botw_nominations_pkey PRIMARY KEY (guild, member);


--
-- TOC entry 2887 (class 2606 OID 65692)
-- Name: botw_settings botw_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.botw_settings
    ADD CONSTRAINT botw_settings_pkey PRIMARY KEY (guild);


--
-- TOC entry 2889 (class 2606 OID 65694)
-- Name: botw_winners botw_winners_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.botw_winners
    ADD CONSTRAINT botw_winners_pkey PRIMARY KEY (id);


--
-- TOC entry 2891 (class 2606 OID 65696)
-- Name: emoji_settings emoji_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.emoji_settings
    ADD CONSTRAINT emoji_settings_pkey PRIMARY KEY (guild);


--
-- TOC entry 2893 (class 2606 OID 65698)
-- Name: greeters greeters_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.greeters
    ADD CONSTRAINT greeters_pkey PRIMARY KEY (guild, type);


--
-- TOC entry 2899 (class 2606 OID 65700)
-- Name: prefixes guild_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.prefixes
    ADD CONSTRAINT guild_settings_pkey PRIMARY KEY (guild);


--
-- TOC entry 2895 (class 2606 OID 65702)
-- Name: idols idols_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.idols
    ADD CONSTRAINT idols_pkey PRIMARY KEY ("group", name);


--
-- TOC entry 2897 (class 2606 OID 65704)
-- Name: mirrors mirrors_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.mirrors
    ADD CONSTRAINT mirrors_pkey PRIMARY KEY (destination, origin);


--
-- TOC entry 2901 (class 2606 OID 65706)
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY ("user");


--
-- TOC entry 2903 (class 2606 OID 65708)
-- Name: reminders reminders_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.reminders
    ADD CONSTRAINT reminders_pkey PRIMARY KEY (id);


--
-- TOC entry 2905 (class 2606 OID 65710)
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: public; Owner: botw-bot
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);


-- Completed on 2020-08-12 16:12:29

--
-- PostgreSQL database dump complete
--

