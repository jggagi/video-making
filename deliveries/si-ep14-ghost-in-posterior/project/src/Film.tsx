import React, {useEffect, useRef, useState} from 'react';
import {
	AbsoluteFill,
	Audio,
	cancelRender,
	continueRender,
	delayRender,
	staticFile,
	useCurrentFrame,
	useVideoConfig,
} from 'remotion';
import timing from '../audio-timing.json';
import lexicon from '../telemetry-lexicon.json';
import rdCache from '../public/rd/gray-scott.json';
import {Geometry} from './Geometry';

const ABYSS = '#020A0E';
const CORAL = '#F43F5E';
const TYPE = '#ECFEFF';
const FACE = '"Heiti SC", "PingFang SC", sans-serif';
const MONO = '"Menlo", monospace';

type FilmProps = {silent?: boolean; cover?: false | 'A' | 'B'};

export const Film: React.FC<FilmProps> = ({silent = false, cover = false}) => {
	const frame = useCurrentFrame();
	const {width} = useVideoConfig();
	const f = cover === 'A' ? 2100 : cover === 'B' ? 3840 : frame;
	const [fontHandle] = useState(() => delayRender('Wait for installed local typography'));
	const hud = useRef<HTMLDivElement>(null);
 const decodedTextures=useRef<HTMLImageElement[]>([]);

	useEffect(() => {
		let live = true;
		Promise.all([document.fonts.ready,...rdCache.snapshots.map(snapshot=>{
 const image=new window.Image();image.src=snapshot.pngDataUri;
 decodedTextures.current.push(image);return image.decode();
 })])
 .then(() => {
				if (!live) return;
				const rows = Array.from(hud.current?.querySelectorAll<HTMLElement>('[data-row]') ?? []);
				for (const row of rows) {
					if (row.scrollWidth > row.clientWidth) {
						throw new Error(`HUD row exceeds its 856px safe width: ${row.textContent ?? ''}`);
					}
				}
				continueRender(fontHandle);
			})
			.catch((error) => cancelRender(error));
		return () => {
			live = false;
		};
	}, [fontHandle]);

	const rows = lexicon.readable_hud;
	const caption = cover
		? undefined
		: timing.captions.find((item) => f >= item.startFrame && f < item.endFrame);
	const quiet = f >= 4860;
	const isCover = Boolean(cover);

	return (
		<AbsoluteFill style={{backgroundColor: ABYSS, color: TYPE, fontFamily: FACE}}>
			<div
				style={{
					position: 'absolute',
					left: 0,
					top: 0,
					width: 1080,
					height: 1920,
					transform: `scale(${width / 1080})`,
					transformOrigin: 'top left',
					background: ABYSS,
					overflow: 'hidden',
				}}
			>
				<svg
					width={1080}
					height={1920}
					viewBox="0 0 1080 1920"
					style={{position: 'absolute', inset: 0}}
					aria-hidden="true"
				>
					<defs>
						<radialGradient id="quiet-aura">
							<stop offset="0%" stopColor="#10B981" stopOpacity="0.18" />
							<stop offset="100%" stopColor="#020A0E" stopOpacity="0" />
						</radialGradient>
						<pattern id="fine-grid" width="36" height="36" patternUnits="userSpaceOnUse">
							<path d="M36 0H0V36" fill="none" stroke="#34D399" strokeOpacity="0.035" strokeWidth="0.6" />
						</pattern>
						<filter id="soft-bokeh" x="-50%" y="-50%" width="200%" height="200%">
							<feGaussianBlur stdDeviation="6" />
						</filter>
						<filter id="fluorescence" x="-50%" y="-50%" width="200%" height="200%">
							<feGaussianBlur stdDeviation="4" />
						</filter>
					</defs>
					<rect width="1080" height="1920" fill="url(#fine-grid)" />
					<ellipse cx="530" cy="930" rx="520" ry="640" fill="url(#quiet-aura)" opacity={quiet ? 0.04 : 0.48} />
					{!quiet &&
						<g filter="url(#soft-bokeh)" opacity="0.08">
							{Array.from({length: 14}, (_, index) => {
								const x = 72 + ((index * 173 + f * (0.08 + (index % 4) * 0.025)) % 850);
								const y = 590 + ((index * 97 + f * (0.035 + (index % 3) * 0.018)) % 680);
								return <circle key={index} cx={x} cy={y} r={2.4 + (index % 3) * 1.4} fill="#34D399" />;
							})}
						</g>}
					<path d="M64 154H920" stroke="#34D399" strokeOpacity="0.34" strokeWidth="1" />
					<Geometry frame={f} />
					<path d="M64 1290H920" stroke="#6366F1" strokeOpacity={quiet ? 0.12 : 0.25} strokeWidth="1" />
				</svg>

				{!isCover && (
					<div
						ref={hud}
						data-hud
						style={{
							position: 'absolute',
							left: 64,
							top: 174,
							width: 856,
							fontFamily: MONO,
							fontSize: 30,
							lineHeight: '33px',
							fontVariantNumeric: 'tabular-nums',
							opacity: quiet ? 0.72 : 0.96,
						}}
					>
						{rows.map((text, index) => (
							<div
								key={text}
								data-row={index}
								style={{
									width: '100%',
									whiteSpace: 'nowrap',
									color: index === 0 ? (f < 600 ? CORAL : '#10B981') : index === 1 ? '#34D399' : '#6366F1',
								}}
							>
								{text}
							</div>
						))}
					</div>
				)}

				{!isCover ? (
					<>
						<div style={{position: 'absolute', left: 64, top: 330, width: 856, fontFamily: MONO, fontSize: 30, lineHeight: '36px', letterSpacing: 1, color: '#34D399'}}>
							一眼万年 · 第三季 // SEASON 03
						</div>
						<div style={{position: 'absolute', left: 64, top: 371, width: 856, fontSize: 60, lineHeight: '68px', fontWeight: 700, letterSpacing: 2, color: TYPE}}>
							死后第七年<br />他还在回微信
						</div>
						<div style={{position: 'absolute', left: 64, top: 514, width: 856, fontFamily: MONO, fontSize: 21, lineHeight: '27px', letterSpacing: 0.8, color: '#34D399', opacity: 0.78}}>
							THE GHOST IN THE POSTERIOR
						</div>
					</>
				) : (
					<div style={{position: 'absolute', left: 64, top: 333, width: 856, fontSize: 62, lineHeight: '78px', fontWeight: 700, letterSpacing: 1, color: TYPE, textShadow: '0 3px 18px #020A0E'}}>
						他去世第七年，<br />依然每天早上七点<br />秒回我的微信
					</div>
				)}

				{!isCover && quiet && (
					<>
						<div style={{position: 'absolute', left: 78, top: 1000, width: 828, textAlign: 'center', fontSize: 41, lineHeight: '56px', fontWeight: 600, color: TYPE, textShadow: '0 2px 10px #020A0E', opacity: 0.86}}>
							“算法从来没有替你复活他。<br />它只是用一个永远不会离开的幻影，<br />替你杀死了他第二次。”
						</div>
						<div style={{position: 'absolute', left: 64, top: 1250, width: 856, textAlign: 'center', fontFamily: MONO, fontSize: 25, letterSpacing: 1.1, color: '#34D399', opacity: 0.68}}>
							一眼万年 · 死后第七年
						</div>
					</>
				)}

				{!isCover && f >= 5160 && f <= 5399 && (
					<div style={{position: 'absolute', left: 64, top: 1324, width: 856, textAlign: 'center', fontSize: 24, lineHeight: '30px', color: TYPE, opacity: 0.35}}>
						未来 SI 思想实验 · 遥测与数值均为虚构
					</div>
				)}

				{caption && (
					<div
						data-caption
						style={{
							position: 'absolute',
							left: 64,
							top: 1388,
							width: 856,
							fontSize: 49,
							lineHeight: '54px',
							fontWeight: 700,
							whiteSpace: 'pre-line',
							textAlign: 'center',
							textShadow: '0 2px 8px #020A0E',
							color: TYPE,
						}}
					>
						{caption.text}
					</div>
				)}
			</div>
			{!silent && <Audio src={staticFile('audio/master.wav')} />}
		</AbsoluteFill>
	);
};
