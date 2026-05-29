// ─────────────────────────────────────────────────────────────────────────────
// OperatorHMI.tsx — HMI de operador de la celda Schneider, portada de la V62.
//
// Réplica en React de `schneider_hmi/src/hmi_node.py` (HMI tkinter de la
// simulación ROS, estable desde V55, recalculada en V61/V62):
//
//   · 4 botones de operador:  START · Colocar CAFI · STOP · RESET
//     (con la misma matriz de habilitación: START=IDLE, CAFI=RUNNING+spawn,
//      STOP=RUNNING, RESET=PAUSED/FAULT)
//   · Estado de celda + etapa de ciclo + veredicto de cámara (PASS/FAIL)
//   · Spawn ALLOWED/BLOCKED + fault
//   · 4 lámparas Digital Input  (Conveyor · Remachado · Visión · Cobot ready)
//   · 8 lámparas Digital Output (Motor · Disco · Remachado · Cámara · Grip x2 ·
//     Solenoide · Reservado)
//
// Se alimenta de un snapshot derivado del ciclo REAL de la celda (SequencePlayer
// en CellViewer3D), e incluye la lectura del contrato del turntable
// (HOME/WORK/RIVETING, limits, remachado) y el contador de la flota de CAFIs.
// Convive con la escena 3D dentro de la pestaña "Celda 3D".
// ─────────────────────────────────────────────────────────────────────────────

import React from 'react';
import type { SimSnapshot } from './turntableSim';

export interface OperatorHMIProps {
  snapshot: SimSnapshot;
  onStart: () => void;
  onCafi: () => void;
  onStop: () => void;
  onReset: () => void;
  /** Contador de la flota de CAFIs (entran / salen / objetivo). */
  cafiIn?: number;
  cafiOut?: number;
  total?: number;
}

const COLOR_OFF = '#3a4a5e';
const COLOR_ON = '#22dd55';
const COLOR_WARN = '#ff5566';

function Lamp({ on, label, warn }: { on: boolean; label: string; warn?: boolean }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, flex: '1 0 0', minWidth: 56 }}>
      <span style={{ fontSize: 16, lineHeight: 1, color: on ? (warn ? COLOR_WARN : COLOR_ON) : COLOR_OFF, textShadow: on ? `0 0 8px ${warn ? COLOR_WARN : COLOR_ON}` : 'none' }}>●</span>
      <span style={{ fontSize: 8.5, color: '#8fa3bd', textAlign: 'center', lineHeight: 1.15 }}>{label}</span>
    </div>
  );
}

function OpButton({ label, color, enabled, onClick }: { label: string; color: string; enabled: boolean; onClick: () => void }) {
  return (
    <button
      onClick={enabled ? onClick : undefined}
      disabled={!enabled}
      style={{
        flex: 1,
        padding: '9px 4px',
        borderRadius: 6,
        border: 'none',
        cursor: enabled ? 'pointer' : 'default',
        background: enabled ? color : '#3b4555',
        color: enabled ? '#fff' : '#7e8a9a',
        fontSize: 10.5,
        fontWeight: 700,
        letterSpacing: 0.3,
        textTransform: 'uppercase',
        transition: 'background 0.15s',
      }}
    >
      {label}
    </button>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ border: '1px solid #1d2c44', background: 'rgba(20,30,48,0.45)', borderRadius: 8, padding: 10 }}>
      <div style={{ fontSize: 8.5, letterSpacing: 1.6, color: '#5f7da3', textTransform: 'uppercase', fontWeight: 600, marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}

function statRow(label: string, value: string, color = '#dde4f0') {
  return (
    <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, padding: '2px 0' }}>
      <span style={{ color: '#7a8c9e' }}>{label}</span>
      <span style={{ color, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}

export default function OperatorHMI({
  snapshot, onStart, onCafi, onStop, onReset, cafiIn, cafiOut, total,
}: OperatorHMIProps) {
  const s = snapshot;
  const tt = s.turntable;

  const startEnabled = s.cell === 'IDLE';
  const cafiEnabled = s.spawnAllowed;
  const stopEnabled = s.cell === 'RUNNING';
  const resetEnabled = s.cell === 'PAUSED' || s.cell === 'FAULT' || s.cell === 'RUNNING';

  const cellColor =
    s.cell === 'FAULT' ? COLOR_WARN : s.cell === 'RUNNING' ? COLOR_ON : s.cell === 'PAUSED' ? '#fbbf24' : '#cbd5e1';
  const verdictColor = s.verdict === 'PASS' ? COLOR_ON : s.verdict === 'FAIL' ? COLOR_WARN : '#5f7da3';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Header */}
      <div>
        <div style={{ fontSize: 9, letterSpacing: 2.5, color: '#22c55e', textTransform: 'uppercase', fontWeight: 600 }}>
          schneider_hmi · V62
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#f1f5f9', letterSpacing: -0.2 }}>
          Operator HMI — Celda de Remachado
        </div>
      </div>

      {/* Operator buttons */}
      <div style={{ display: 'flex', gap: 6 }}>
        <OpButton label="Start" color="#22aa55" enabled={startEnabled} onClick={onStart} />
        <OpButton label="CAFI" color="#3399ff" enabled={cafiEnabled} onClick={onCafi} />
        <OpButton label="Stop" color="#dd5500" enabled={stopEnabled} onClick={onStop} />
        <OpButton label="Reset" color="#a23bff" enabled={resetEnabled} onClick={onReset} />
      </div>

      {/* Contador de flota de CAFIs */}
      {total ? (
        <div style={{ display: 'flex', gap: 6 }}>
          <div style={{ flex: 1, textAlign: 'center', padding: '5px 0', borderRadius: 5, fontSize: 10, fontWeight: 700, color: '#dde4f0', background: 'rgba(34,170,85,0.18)', border: '1px solid #22aa5566' }}>
            CAFI IN: {cafiIn ?? 0}/{total}
          </div>
          <div style={{ flex: 1, textAlign: 'center', padding: '5px 0', borderRadius: 5, fontSize: 10, fontWeight: 700, color: '#dde4f0', background: 'rgba(59,139,255,0.18)', border: '1px solid #3b8bff66' }}>
            CAFI OUT: {cafiOut ?? 0}/{total}
          </div>
        </div>
      ) : null}

      {/* Cell state */}
      <Section title="Cell State">
        {statRow('Celda', s.cell, cellColor)}
        {statRow('Etapa', s.cycleStage)}
        {statRow('Cámara', s.verdict || '--', verdictColor)}
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          <div style={{ flex: 1, textAlign: 'center', padding: '4px 0', borderRadius: 5, fontSize: 9, fontWeight: 700, color: '#fff', background: s.spawnAllowed ? COLOR_ON : COLOR_WARN }}>
            {s.spawnAllowed ? 'SPAWN ALLOWED' : 'SPAWN BLOCKED'}
          </div>
          {s.faultReason ? (
            <div style={{ flex: 1, textAlign: 'center', padding: '4px 0', borderRadius: 5, fontSize: 9, fontWeight: 700, color: '#fff', background: COLOR_WARN }}>
              {s.faultReason}
            </div>
          ) : null}
        </div>
      </Section>

      {/* Turntable contract (mesa rotatoria — contrato nuevo) */}
      <Section title="Mesa Rotatoria (turntable)">
        {statRow('Posición', tt.position, tt.position === 'ERROR' ? COLOR_WARN : '#a78bfa')}
        {statRow('Ángulo', `${tt.angle_deg.toFixed(1)}°`)}
        {statRow('Target', tt.target)}
        {statRow('Dirección', tt.last_direction)}
        {statRow('Remachando', tt.riveting ? 'SÍ' : 'no', tt.riveting ? '#fb923c' : '#7a8c9e')}
        {statRow('Remache listo', tt.riveting_done ? 'SÍ' : 'no', tt.riveting_done ? COLOR_ON : '#7a8c9e')}
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          <div style={{ flex: 1, textAlign: 'center', padding: '4px 0', borderRadius: 5, fontSize: 9, fontWeight: 700, color: '#fff', background: tt.limit_home ? COLOR_ON : COLOR_OFF }}>
            LIMIT HOME
          </div>
          <div style={{ flex: 1, textAlign: 'center', padding: '4px 0', borderRadius: 5, fontSize: 9, fontWeight: 700, color: '#fff', background: tt.limit_work ? COLOR_ON : COLOR_OFF }}>
            LIMIT WORK
          </div>
        </div>
        <div style={{ fontSize: 10, color: '#9bb0c8', marginTop: 8, fontStyle: 'italic' }}>{tt.message}</div>
      </Section>

      {/* Digital Inputs */}
      <Section title="Digital Inputs (4)">
        <div style={{ display: 'flex', gap: 4 }}>
          <Lamp on={s.di.conveyor} label="Conveyor" />
          <Lamp on={s.di.rivet} label="Remachado" />
          <Lamp on={s.di.vision} label="Visión" />
          <Lamp on={s.di.cobotReady} label="Cobot ready" />
        </div>
      </Section>

      {/* Digital Outputs */}
      <Section title="Digital Outputs (8)">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          <Lamp on={s.do.convMotor} label="Conv Motor" />
          <Lamp on={s.do.disco} label="Disco" />
          <Lamp on={s.do.remachado} label="Remachado" warn />
          <Lamp on={s.do.camara} label="Cámara" />
          <Lamp on={s.do.gripOpen} label="Grip Open" />
          <Lamp on={s.do.gripClose} label="Grip Close" />
          <Lamp on={s.do.solLeft} label="Sol Left" />
          <Lamp on={s.do.reservado} label="Reservado" />
        </div>
      </Section>

      {/* Modo */}
      <div style={{ fontSize: 9, color: '#5f7da3', textAlign: 'center', letterSpacing: 0.5 }}>
        MODO SIMULACIÓN (mock) · contrato /ws/turntable
      </div>
    </div>
  );
}
