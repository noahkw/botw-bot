CREATE TABLE public.roles
(
    guild bigint NOT NULL,
    role bigint NOT NULL,
    clear_after integer,
    active boolean NOT NULL,
    CONSTRAINT roles_pkey PRIMARY KEY (role)
)

TABLESPACE pg_default;

ALTER TABLE public.roles
    OWNER to "botw-bot";

CREATE TABLE public.role_aliases
(
    role bigint NOT NULL,
    guild bigint NOT NULL,
    alias character varying(255) COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT role_aliases_pkey PRIMARY KEY (alias, guild),
    CONSTRAINT role_aliases_role_fk FOREIGN KEY (role)
        REFERENCES public.roles (role) MATCH SIMPLE
        ON UPDATE CASCADE
        ON DELETE CASCADE
        DEFERRABLE
        NOT VALID
)

TABLESPACE pg_default;

ALTER TABLE public.role_aliases
    OWNER to "botw-bot";

CREATE TABLE public.role_clears
(
    role bigint NOT NULL,
    member bigint NOT NULL,
    "when" timestamp with time zone NOT NULL,
    guild bigint NOT NULL,
    CONSTRAINT role_clears_pkey PRIMARY KEY (role, member)
)

TABLESPACE pg_default;

ALTER TABLE public.role_clears
    OWNER to "botw-bot";
