CREATE TABLE aluno (
  id uuid NOT NULL,
  nome_aluno character varying NOT NULL,
  sobrenome_aluno character varying NOT NULL,
  email_institucional character varying NOT NULL UNIQUE,
  matricula_ra character NOT NULL UNIQUE,
  semestre integer NOT NULL,
  turma character NOT NULL,
  id_curso uuid NOT NULL,
  CONSTRAINT aluno_pkey PRIMARY KEY (id),
  CONSTRAINT aluno_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

CREATE TABLE alunodisciplina (
  id_aluno uuid NOT NULL,
  id_disciplina uuid NOT NULL,
  CONSTRAINT alunodisciplina_pkey PRIMARY KEY (id_aluno, id_disciplina),
  CONSTRAINT alunodisciplina_id_aluno_fkey FOREIGN KEY (id_aluno) REFERENCES public.aluno(id),
  CONSTRAINT alunodisciplina_id_disciplina_fkey FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina),
  CONSTRAINT fk_disciplina FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina)
);

CREATE TABLE avaliacao (
  id_avaliacao uuid NOT NULL DEFAULT gen_random_uuid(),
  tipo_avaliacao character varying NOT NULL CHECK (tipo_avaliacao::text = ANY (ARRAY['NP1'::character varying, 'NP2'::character varying, 'SUB'::character varying, 'EXAME'::character varying]::text[])),
  data_prova date NOT NULL,
  hora_inicio time without time zone,
  hora_fim time without time zone,
  sala character varying,
  conteudo character varying,
  id_disciplina uuid NOT NULL,
  id_aplicador uuid,
  CONSTRAINT avaliacao_pkey PRIMARY KEY (id_avaliacao),
  CONSTRAINT fk_disciplina FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina),
  CONSTRAINT fk_aplicador_professor FOREIGN KEY (id_aplicador) REFERENCES public.professor(id)
);

CREATE TABLE aviso (
  id_aviso uuid NOT NULL DEFAULT gen_random_uuid(),
  titulo text NOT NULL,
  conteudo text NOT NULL,
  data timestamp without time zone NOT NULL,
  id_professor uuid,
  id_coordenador uuid,
  id_disciplina uuid,
  CONSTRAINT aviso_pkey PRIMARY KEY (id_aviso),
  CONSTRAINT fk_professor FOREIGN KEY (id_professor) REFERENCES public.professor(id),
  CONSTRAINT fk_coordenador FOREIGN KEY (id_coordenador) REFERENCES public.coordenador(id),
  CONSTRAINT fk_disciplina FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina)
);

CREATE TABLE baseconhecimento (
  id_conhecimento uuid NOT NULL DEFAULT gen_random_uuid(),
  nome_arquivo_origem text,
  categoria character varying,
  status character varying NOT NULL DEFAULT 'rascunho'::character varying,
  criado_em timestamp with time zone DEFAULT now(),
  id_disciplina uuid,
  conteudo_processado text,
  palavra_chave jsonb DEFAULT '[]'::jsonb,
  embedding USER-DEFINED,
  fts tsvector,
  url_documento text,
  id_tcc uuid,
  id_aps uuid,
  id_estagio uuid,
  id_horas_complementares uuid,
  CONSTRAINT baseconhecimento_pkey PRIMARY KEY (id_conhecimento),
  CONSTRAINT fk_disciplina FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina),
  CONSTRAINT fk_tcc FOREIGN KEY (id_tcc) REFERENCES public.trabalho_academico(id_trabalho),
  CONSTRAINT fk_aps FOREIGN KEY (id_aps) REFERENCES public.trabalho_academico(id_trabalho),
  CONSTRAINT fk_estagio FOREIGN KEY (id_estagio) REFERENCES public.trabalho_academico(id_trabalho),
  CONSTRAINT fk_horas_complementares FOREIGN KEY (id_horas_complementares) REFERENCES public.trabalho_academico(id_trabalho)
);

CREATE TABLE coordenador (
  id uuid NOT NULL,
  id_funcional character varying NOT NULL UNIQUE,
  nome_coordenador character varying NOT NULL,
  sobrenome_coordenador character varying NOT NULL,
  email_institucional character varying NOT NULL UNIQUE,
  departamento character varying NOT NULL,
  dias_atendimento jsonb NOT NULL DEFAULT '[]'::jsonb,
  atendimento_hora_inicio time without time zone,
  atendimento_hora_fim time without time zone,
  CONSTRAINT coordenador_pkey PRIMARY KEY (id),
  CONSTRAINT coordenador_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

CREATE TABLE coordenadorcurso (
  id_coordenador uuid NOT NULL,
  id_curso uuid NOT NULL,
  CONSTRAINT coordenadorcurso_pkey PRIMARY KEY (id_coordenador, id_curso),
  CONSTRAINT fk_coordenador FOREIGN KEY (id_coordenador) REFERENCES public.coordenador(id)
);

CREATE TABLE cronograma (
  id_cronograma uuid NOT NULL DEFAULT gen_random_uuid(),
  nome_disciplina text NOT NULL,
  dia_semana integer CHECK (dia_semana >= 1 AND dia_semana <= 7),
  hora_inicio time without time zone,
  hora_fim time without time zone,
  tipo_aula character varying,
  sala integer,
  andar integer,
  bloco character,
  periodicidade character varying NOT NULL DEFAULT 'semanal'::character varying,
  data_inicio_semestre date,
  data_fim_semestre date,
  id_disciplina uuid NOT NULL,
  CONSTRAINT cronograma_pkey PRIMARY KEY (id_cronograma),
  CONSTRAINT fk_disciplina FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina)
);

CREATE TABLE curso (
  id_curso uuid NOT NULL DEFAULT gen_random_uuid(),
  nome_curso text NOT NULL,
  formacao text NOT NULL,
  periodo integer,
  carga_horaria interval,
  modalidade jsonb DEFAULT '[]'::jsonb,
  descricao text,
  CONSTRAINT curso_pkey PRIMARY KEY (id_curso)
);

CREATE TABLE cursodisciplina (
  id_curso uuid NOT NULL,
  id_disciplina uuid NOT NULL,
  CONSTRAINT cursodisciplina_pkey PRIMARY KEY (id_curso, id_disciplina),
  CONSTRAINT cursodisciplina_id_disciplina_fkey FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina),
  CONSTRAINT fk_disciplina FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina)
);

CREATE TABLE disciplina (
  id_disciplina uuid NOT NULL DEFAULT gen_random_uuid(),
  nome_disciplina text NOT NULL,
  codigo character NOT NULL,
  semestre character NOT NULL,
  carga_horaria integer NOT NULL DEFAULT 0,
  ementa character varying,
  CONSTRAINT disciplina_pkey PRIMARY KEY (id_disciplina)
);

CREATE TABLE mensagemaluno (
  id_mensagem uuid NOT NULL DEFAULT gen_random_uuid(),
  primeira_pergunta text NOT NULL,
  topico jsonb DEFAULT '[]'::jsonb,
  feedback text NOT NULL,
  data_hora timestamp without time zone NOT NULL,
  CONSTRAINT mensagemaluno_pkey PRIMARY KEY (id_mensagem)
);

CREATE TABLE professor (
  id uuid NOT NULL,
  nome_professor character varying NOT NULL,
  id_funcional character varying NOT NULL UNIQUE,
  sobrenome_professor character varying NOT NULL,
  email_institucional character varying NOT NULL UNIQUE,
  dias_atendimento jsonb NOT NULL DEFAULT '[]'::jsonb,
  atendimento_hora_inicio time without time zone,
  atendimento_hora_fim time without time zone,
  CONSTRAINT professor_pkey PRIMARY KEY (id),
  CONSTRAINT professor_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

CREATE TABLE professordisciplina (
  id_professor uuid NOT NULL,
  id_disciplina uuid NOT NULL,
  CONSTRAINT professordisciplina_pkey PRIMARY KEY (id_professor, id_disciplina),
  CONSTRAINT fk_professor FOREIGN KEY (id_professor) REFERENCES public.professor(id),
  CONSTRAINT fk_disciplina FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina)
);

CREATE TABLE trabalho_academico (
  id_trabalho uuid NOT NULL DEFAULT gen_random_uuid(),
  tipo USER-DEFINED NOT NULL,
  tema text NOT NULL,
  regras text,
  data_entrega date,
  maximo_integrantes integer,
  semestre character varying,
  id_orientador uuid,
  id_curso uuid NOT NULL,
  id_disciplina uuid,
  id_coordenador uuid,
  CONSTRAINT trabalho_academico_pkey PRIMARY KEY (id_trabalho),
  CONSTRAINT fk_orientador FOREIGN KEY (id_orientador) REFERENCES public.professor(id),
  CONSTRAINT fk_curso FOREIGN KEY (id_curso) REFERENCES public.curso(id_curso),
  CONSTRAINT fk_disciplina FOREIGN KEY (id_disciplina) REFERENCES public.disciplina(id_disciplina),
  CONSTRAINT fk_coordenador FOREIGN KEY (id_coordenador) REFERENCES public.coordenador(id)
);