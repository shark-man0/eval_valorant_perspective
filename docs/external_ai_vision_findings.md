# External AI: Vision側の所見

本作業では `hud/` `visual/` `maps/` `application/hud_video_processor.py` を変更していない。

現時点で、Vision側のコードを根拠にした未解決の所見はない（Vision側コードは未精査）。

参考: `player_specific_hud_valid=false` 時の `spike_state` が視点相対のまま後段へ渡る点は、
Vision側のvalidatorが `hp/armor/ammo/weapon/ability` のみnull強制しているために起きる。
本作業では後段（`rounds/builder.py`）で安全側にマスクして対処した。
Vision側でも `spike_state` を同様に扱うかどうかは、Vision担当の判断に委ねる。
