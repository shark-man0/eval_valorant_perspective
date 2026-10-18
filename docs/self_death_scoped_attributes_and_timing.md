# Self Death：クラス別属性資格とnative時刻の確認

判定は **B**。実験用の属性資格をクラス範囲で制限できるようにした。
一方、実資格certificateと正式Deathは未成立であり、canonical精度改善の完了ではない。
開始mainは `7e480c2f2f7f49aea73e1541d065d78881d2f11c`、開始ブランチは
`d5c90242aa705cc27de5c486ebf246acfc9e84f3`。PR #53のstackと既存安全契約を維持する。

## 具体的な問題

[固定source測定](self_death_fixed_source_component_audit.md) では、未変更のReport readerが
Razeのportraitを正しく読んだ。しかし、Fadeの独立した正例は得られていない。
従来の内部 `numeric_self_death_attributes_v1` はproducer全体に対する意味reviewを要求し、
その資格の中でportraitクラスを限定する仕組みはなかった。
Raze一例の成功から全対応クラスをqualifiedとするのは不適切である。
実資格が存在しない現状では誤った正式出力は発生していないが、部分的な資格付けを
正しく表現できないため、認識済みクラスと未検証クラスを分ける必要がある。

## 内部v2資格契約

`QualifiedDeathAttributeContract` に、明示的に選択する内部certificate v2を追加した。
v2はv1の既存項目に、`qualified_killer_agent_labels` だけを追加する。
値は独立reviewで資格を確認した**出力ラベルと完全一致する文字列**の非空・重複なしlist。
bool、数値、dict、空白だけの文字列、前後空白、欠落、未知の追加keyを拒否する。
大文字小文字や文字列の別名を自動的に同一視しない。

projection時、元のepisode内のportrait候補が範囲外なら `killer_agent` を出力せず、
`killer_agent:portrait_class_not_qualified` を記録する。
その値を近いクラスへ補正しない。別の候補に都合よく置き換えない。
許可クラスと範囲外クラスが競合している場合も、元の全field conflict拒否を維持する。
独立にqualifiedされたvictim名やdamageまで、クラス範囲不足だけで破棄しない。
count用の資格とpointに必要な属性用の資格も引き続き分離する。

クラス範囲の一致だけでは属性は成立しない。以下をすべて従来どおり要求する。

- 元のDeath event qualificationと実画像のsource-player／victim／temporal証拠。
- 外部から与えられたreview済みreport digest、parent資格、現在のrelease fingerprint。
- split review、3属性のsemantic review、元Report／fatal-row producerのfingerprint。
- 元field自身のsource PTS・pixel・ROI・confidenceと、同一frameのqualified Self支持。
- killer portraitと同じframeのfatal damage row。Reportやportrait単独では成立しない。
- conflict、欠落、不正confidence、別source／segment／時刻の証拠の拒否。

**クラス範囲は資格の上限であり、資格自体を生成するものではない。**
実際のクラス名やGTをproductionに埋め込まず、今回Raze用の実資格を発行したわけでもない。
v2にも3属性のreviewを要求し、Subjectがunknownなら正式Deathは生成しない。

## 互換性と適用範囲

これは実験用の内部qualification fileのversion追加である。
公開HUD／Event／Round Package Schema、SQLiteテーブル、Trace、GUI、identity authority、
reader confidence、threshold、既存event actor、source continuity、default callerは変更しない。
Eventに出力されるfieldとprovenanceの形も維持する。

v1のキーとproducer全体のreview契約はそのまま読める。v1へ範囲keyを足したものを
黙って範囲なしとして受理しない。v2のscope欠落をv1へfallbackしない。
既存の無資格defaultは出力0のままである。
consumerのコードは変わるため、release fingerprintも変わる。過去のcertificateを
現在の実装へ付け替えるmigrationや再署名は行わない。
範囲を変更したcertificateはdigestも変わり、以前のcheckpointを復元できない。
外部で信頼したdigestを変えずにファイル内で許可クラスを増やすことも拒否する。

既存のnative Event→Package→Fact→Trace→SQLite経路で、v1／v2の許可クラス、
v2範囲外クラス、count-onlyを合成契約テストした。
元onsetへのRound所属、actor、時刻、confidence、属性provenance、保存・Schema整合性を維持し、
HUD identityやHP／Alive／Weaponへ証拠を流用していない。
合成成功は実画像の資格付けやcanonical PASSではない。

## Death時刻のsource画像による確認

既にfreeze・連続decode・source review・認識が終わっていたcase005について、
元native画像を読み、最後の生存表示と最初の死亡表示を確認した。
これは保存済み候補を見た後のretrospective reviewであり、新規blind holdoutではない。
元の認識前coarse reviewも残しており、後から認識前に精密時刻を付けたように扱わない。

判断にtimerやGT時刻は使っていない。直前の生存first-personの武器・HP表示に続いて、
武器とbottom HUDが消え、視点が死亡animationへ移り、self-referential Reportと
描画途中のkillfeedが現れる。後続では、白いweaponの右側に録画本人の黄色victim枠、
左側にnonself killerがあることも元画像で確認した。
Reportだけ、spectatorだけ、damageだけを死亡の根拠にしていない。

最後の生存画像と最初の死亡表示はnative cadenceで隣接し、間隔は1/60秒。
保存された候補onsetは、その可視遷移区間から **16.667〜33.333ms後** にある。
confirmationは元onsetから0.300秒後で、元onsetをconfirmationへ動かしていない。
これは可視client-side presentationに対する既知1例の確認であり、server内部の死亡時刻や
独立したGT単一点に対する誤差測定ではない。canonical窓へ時刻を補正していない。

元v4、weapon参照追加後、名前layout修正後の保存出力は、いずれもこの151連続frameに
候補1件で、onset／confirmation／supportが一致した。
`self_death_image.py` と `report_victim_episode.py` のファイル全体が、case005認識前freeze
`4e1fbe3` と現在でbyte一致することも確認した。horizonをこの例に合わせて変更していない。
一方、case005は後のweapon／name開発に使われているため、reader全体の独立holdoutではない。
元manifest、encoded／pixel hash、epoch、native PTS、review、各変種の出力hashをprivateに保存した。

## Report再表示の負例から分かった制約

同じfreezeに含まれるcase006は121連続frameで、全変種とも候補0件である。
元画像では、購入menuが閉じると、生存first-personのHPと既存のYoru Reportが再表示される。
新しいkillfeedや死亡animationはない。readerにもvictimは出ていない。

重要なのは、menuで隠れていたcaptionが後にNCC 0.90以上になっても、
それだけで「新しいReportが発生した」とは言えないことである。
この負例で出力0だったことは確認できるが、**Report absence readerが独立資格付け済みという
証明にはならない**。遮蔽／menuでの未検出をqualified absenceと見なさない。
現在のnumeric victim条件が負例を拒否したことと、Report transition単体の資格を分けて記録する。
今後のevent資格には、このabsence／occlusion問題の独立reviewも必要である。

## テストと実画像評価の区別

v1互換、v2範囲内／外、case違い、無効scope、未許可scope拡張、Subject資格欠落、
fatal-row欠落、範囲外クラスとのconflict、checkpoint不一致を確認する。
既存のconfidence・owner・source・temporalテストとPackage／Trace／SQLiteの検証も維持する。
関連consumer／sessionを含む138ケースは32.08秒でPASS、その後の不正schema型2ケースを含む
属性関連の最終64ケースは2.78秒でPASS。これらは重複を含むため合算しない。
native Package／Fact／Trace／SQLiteの4モードもPASS。
Ruff、mypy（148 source files）、classified text-I/O auditはPASSした。
現在HEADのLinux／Windows CI結果はPR #53の当該commitのcheckを正とする。
旧commit `d5c9024` の4,322 PASS・87.19%を新commitの成功として流用しない。

| 指標 | Previous | Current | Delta |
| --- | --- | --- | --- |
| killer-agent資格範囲 | v1のproducer全体 | v1維持＋明示v2のクラス範囲 | 部分reviewを限定可能 |
| reader／temporalの判定条件 | 固定 | 不変 | 0 |
| case005保存候補／case006保存候補 | 1 / 0 | 同じ保存source出力を監査 | 認識改善として加算しない |
| 正式Death | 0 | 0 | 0 |
| 新コードtargeted／sampled／Full | 未計測 | 未計測 | 未計測 |

正式基準23/55/4、保存した未採用Strict 28/50/4、別時刻方式30/49/3は区別したまま。
今回、新規canonical PASSや既存PASS→FAILなしとは主張しない。
実資格と正式positiveが未成立なのでFullは実行していない。

残る最初の阻害条件は、current-profileの独立Self Victim・Report transition／absence・
negative episode資格である。Razeの画像候補と現在のv2だけでこれを代替しない。
Fadeの独立positiveや、native applicationの実資格付き呼び出しとcanonical比較も未完了。
資格が成立したときに、確認済みのクラスだけを正式属性へ運ぶ経路が今回の実装成果である。
