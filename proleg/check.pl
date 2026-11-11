:- encoding(utf8).

% PROLEG 統合チェック
%   1. ルールベースのロード（コンパイル）
%   2. style_check
%   3. library(check)
%   4. plunit による代表条文の推論検証
%
% 実行:
%   swipl proleg/check.pl

:- set_prolog_flag(encoding, utf8).

:- style_check(+singleton).
:- style_check(+no_effect).
:- style_check(+var_branches).

:- consult('prolegEng3.pl').
:- messageoff.

:- absolute_file_name('../laws/act/129/129AC0000000089.pl', RuleFile,
                      [access(read)]),
   load_files(RuleFile, [if(true)]).

:- use_module(library(check)).
:- use_module(library(plunit)).

cleanup_facts :-
    retractall(fact(_)).

assert_facts([]).
assert_facts([F|Fs]) :-
    assertz(fact(F)),
    assert_facts(Fs).

with_facts(Facts, Goal) :-
    setup_call_cleanup(
        assert_facts(Facts),
        call(Goal),
        cleanup_facts
    ).

:- begin_tests(民法第5条).

test(未成年者の法律行為の取消, [true(R == true)]) :-
    with_facts(
        [ 未成年者_f(甲),
          法律行為_f(甲, 本件契約),
          法定代理人の同意なし_f(本件契約)
        ],
        (answer(取消可能(本件契約)) -> R = true ; R = false)
    ).

test(ただし書により取消不可, [true(R == false)]) :-
    with_facts(
        [ 未成年者_f(甲),
          法律行為_f(甲, 本件贈与受領),
          法定代理人の同意なし_f(本件贈与受領),
          単に権利を得又は義務を免れる行為_f(本件贈与受領)
        ],
        (answer(取消可能(本件贈与受領)) -> R = true ; R = false)
    ).

:- end_tests(民法第5条).

:- begin_tests(民法第96条).

test(詐欺取消, [true(R == true)]) :-
    with_facts(
        [ 意思表示_f(甲, 本件意思表示),
          詐欺_f(乙, 甲, 本件意思表示)
        ],
        (answer(取消可能(本件意思表示)) -> R = true ; R = false)
    ).

:- end_tests(民法第96条).

:- begin_tests(民法第709条).

test(不法行為の成立, [true(R == true)]) :-
    with_facts(
        [ 故意又は過失_f(甲),
          権利侵害_f(甲, 乙),
          損害の発生_f(乙, 本件損害),
          因果関係_f(甲, 本件損害)
        ],
        (answer(損害賠償義務(甲, 乙, 本件損害)) -> R = true ; R = false)
    ).

test(過失相殺で阻却, [true(R == false)]) :-
    with_facts(
        [ 故意又は過失_f(甲),
          権利侵害_f(甲, 乙),
          損害の発生_f(乙, 本件損害),
          因果関係_f(甲, 本件損害),
          過失相殺_f(乙)
        ],
        (answer(損害賠償義務(甲, 乙, 本件損害)) -> R = true ; R = false)
    ).

:- end_tests(民法第709条).

:- begin_tests(民法第522条).

test(契約成立, [true(R == true)]) :-
    with_facts(
        [ 申込み_f(甲, 本件契約),
          承諾_f(乙, 本件契約)
        ],
        (answer(契約成立(本件契約)) -> R = true ; R = false)
    ).

:- end_tests(民法第522条).

:- initialization(main, main).

main :-
    format('== library(check) ==~n', []),
    check,
    format('~n== plunit ==~n', []),
    (   run_tests
    ->  format('~nALL CHECKS PASSED~n', []),
        halt(0)
    ;   format('~nCHECKS FAILED~n', []),
        halt(1)
    ).
