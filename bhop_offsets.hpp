// Auto bhop offset sources: IDA-style signatures for client.dll code refs plus
// a small fallback table for when a scan misses or its result fails live
// validation. Fallback values refreshed 2026-09-24 from a2x/cs2-dumper main
// output (offsets.json -> dw* globals, client_dll.json -> netvar fields);
// the m_* entries were re-verified unchanged, only the dw* globals moved:
//   https://github.com/a2x/cs2-dumper
// Signatures are not verified across builds — the resolver always cross-checks
// candidates against the live process and falls back to the values below, and
// if neither validates, the feature auto-disables with a status message.
// The pawn chain is only checked while the local controller reports the player
// spawned: dead players' dwLocalPlayerPawn holds a stale freed object that
// fails every static check, which is a wait state, not an offset error.

#pragma once

#include <cstddef>
#include <cstdint>

namespace bhop {
    // rip-relative load in client.dll code:
    //   target RVA = match RVA + instrLen + *(int32_t*)(match + dispAt)
    struct CodeSig {
        const char* ida;
        int         instrLen;   // instruction length incl. the disp32
        int         dispAt;     // byte offset of the disp32 inside the instruction
    };

    inline constexpr CodeSig kEntityListSigs[] = {
        { "48 8B 0D ? ? ? ? 48 8B D1 E8",     7, 3 },  // mov rcx, [rip+X]; mov rdx, rcx; call
        { "48 8B 05 ? ? ? ? 48 85 C0 74",     7, 3 },  // mov rax, [rip+X]; test rax, rax; jz
    };

    inline constexpr CodeSig kLocalPawnSigs[] = {
        { "48 8B 05 ? ? ? ? 48 85 C0 74",     7, 3 },  // mov rax, [rip+X]; test rax, rax; jz
        { "48 8B 05 ? ? ? ? 48 85 C0 0F 84",  7, 3 },  // same, jz near form
    };

    // netvar fields: resolved by locating the schema name string in client.dll,
    // then the SchemaClassFieldData { name*, type*, offset u32 } pointing at it;
    // lo/hi bound the offset dword so a wrong struct match is rejected
    struct NetvarSpec {
        const char*    name;
        std::ptrdiff_t lo;
        std::ptrdiff_t hi;
    };

    inline constexpr NetvarSpec kNetvars[] = {
        { "m_fFlags",           0x200,  0x4000 },  // C_BaseEntity
        { "m_pMovementServices", 0x400, 0x4000 },  // C_BasePlayerPawn
        { "m_nButtons",         0x10,   0x400    },// CPlayer_MovementServices
        { "m_bPawnIsAlive",     0x800,  0xA00 },   // CCSPlayerController
        { "m_hPlayerPawn",      0x800,  0xA00 },   // CCSPlayerController (CHandle u32)
        { "m_bIsLocalPlayerController", 0x600, 0x900 }, // CBasePlayerController
    };

    // IN_JUMP — button bit written for one tick in Memory mode
    inline constexpr uint32_t kInJump = 1u << 1;
    // FL_ONGROUND — m_fFlags bit read for the air/ground edge
    inline constexpr uint32_t kOnGround = 1u << 0;

    // fallback values; dw* globals come from offsets.json, fields from
    // client_dll.json (refreshed 2026-09-24)
    struct Fallback {
        std::ptrdiff_t entityList;
        std::ptrdiff_t localPawn;
        std::ptrdiff_t controller;
        std::ptrdiff_t flags;
        std::ptrdiff_t moveSvc;
        std::ptrdiff_t buttons;
        std::ptrdiff_t pawnAlive;
        std::ptrdiff_t pawnHandle;
        std::ptrdiff_t isLocalCtrl;
        std::ptrdiff_t sceneNode;
        std::ptrdiff_t health;
    };

    inline constexpr Fallback kFallback = {
        0x2711048,   // client.dll::dwEntityList
        0x255C5A8,   // client.dll::dwLocalPlayerPawn
        0x25334D8,   // client.dll::dwLocalPlayerController
        0x3F4,       // C_BaseEntity::m_fFlags
        0x1330,      // C_BasePlayerPawn::m_pMovementServices
        0x50,        // CPlayer_MovementServices::m_nButtons
        0x934,       // CCSPlayerController::m_bPawnIsAlive
        0x92C,       // CCSPlayerController::m_hPlayerPawn
        0x790,       // CBasePlayerController::m_bIsLocalPlayerController
        0x330,       // C_BaseEntity::m_pGameSceneNode
        0x34C,       // C_BaseEntity::m_iHealth
    };
}
