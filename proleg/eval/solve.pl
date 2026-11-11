:- encoding(utf8).

% PROLEG 1 照会ドライバ
% 使い方:
%   swipl -q -t halt \
%     -g "consult('solve.pl'), run('rules.pl', 'facts.json', 'GoalTerm', 'out.txt')"
%
% facts.json は ["未成年者_f(甲)", "法律行為_f(甲, 本件契約)"] の JSON 配列。
% GoalTerm は Prolog 項の文字列。out.txt に true / false を書く。

:- set_prolog_flag(encoding, utf8).
:- use_module(library(http/json)).
:- use_module(library(lists)).

run(RuleFile, FactsFile, GoalAtom, OutFile) :-
    absolute_file_name(RuleFile, RuleAbs, [access(read)]),
    absolute_file_name(FactsFile, FactsAbs, [access(read)]),
    absolute_file_name('../prolegEng3.pl', EngAbs, [access(read)]),
    load_files(EngAbs, [if(true), silent(true)]),
    ignore(messageoff),
    load_files(RuleAbs, [if(true), silent(true)]),
    retractall(fact(_)),
    setup_call_cleanup(
        open(FactsAbs, read, In, [encoding(utf8)]),
        json_read_dict(In, Facts),
        close(In)
    ),
    maplist(assert_fact_string, Facts),
    term_string(Goal, GoalAtom, [syntax_errors(error)]),
    (   catch(answer(Goal), _, fail)
    ->  Result = true
    ;   Result = false
    ),
    setup_call_cleanup(
        open(OutFile, write, Out, [encoding(utf8)]),
        format(Out, '~w~n', [Result]),
        close(Out)
    ).

assert_fact_string(Str) :-
    atom_string(A, Str),
    term_string(Term, A, [syntax_errors(error)]),
    assertz(fact(Term)).
