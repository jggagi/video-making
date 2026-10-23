import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Audio, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame} from 'remotion';
import {Scene} from './Scene';
import captions from '../captions.json';

const IVORY = '#E0F2FE';
const GOLD = '#FACC15';
const CAPTION = '#F3E8C8';
const SILVER = '#A7BBC9';
const clamp = (value: number): number => Math.min(1, Math.max(0, value));
type Caption = {startFrame: number; endFrame: number; text: string};

const captionLines = (text: string): string[] => {
	const paragraphs = text.split('\n').filter(Boolean);
	const lines: string[] = [];
	for (const paragraph of paragraphs) {
		const chars = Array.from(paragraph);
		for (let offset = 0; offset < chars.length; offset += 17) lines.push(chars.slice(offset, offset + 17).join(''));
	}
	if (lines.length > 2) throw new Error('An EP18 caption must fit within two 17-character lines.');
	return lines;
};

export const Film: React.FC<{silent?: boolean; cover?: false | 'A' | 'B'}> = ({silent = false, cover = false}) => {
	const currentFrame = useCurrentFrame();
	const frame = cover === 'A' ? 3960 : cover === 'B' ? 2160 : currentFrame;
	const [fontHandle] = useState(() => delayRender('EP18 local Songti / PingFang typography'));
	useEffect(() => {
		document.fonts.ready
			.then(() => continueRender(fontHandle))
			.catch((error) => cancelRender(error instanceof Error ? error : new Error(String(error))));
	}, [fontHandle]);

	const cap = !cover && (captions as Caption[]).find((item) => frame >= item.startFrame && frame < item.endFrame);
	const lines = cap ? captionLines(cap.text) : [];
	const closing = clamp((frame - 5160) / 75);
	const stamp = clamp((frame - 5010) / 50);

	return (
		<AbsoluteFill style={{background: '#060709', color: IVORY, fontFamily: '"Songti SC", "PingFang SC", serif'}}>
			<Scene frame={frame}/>
			<svg
				width="2160"
				height="3840"
				viewBox="0 0 1080 1920"
				role="presentation"
				style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}
			>
				{!cover && frame < 4860 && <g fontFamily="Menlo, monospace" fontSize="31" letterSpacing="0.15">
					<text x="65" y="200" fill={IVORY}>SURFACE: PUBLIC MODEL</text>
					<text x="65" y="240" fill={IVORY}>DEPTHS: PRIVATE BY CHOICE</text>
					<text x="65" y="280" fill={GOLD}>SHARING: CONSENT REQUIRED</text>
				</g>}

				{!cover && frame < 4860 && <g>
					<text x="68" y="338" fontFamily="Menlo, monospace" fontSize="23" letterSpacing="1.8" fill={SILVER}>
						一眼万年 / 全系列终章 EP.18
					</text>
					<text x="64" y="410" fontSize="62" fontWeight="600" letterSpacing="2" fill={IVORY}>
						心印潜流
					</text>
					<text x="68" y="451" fontFamily="Menlo, monospace" fontSize="22" letterSpacing="1.5" fill={SILVER}>
						THE SPARK WE KEEP
					</text>
					{frame < 600 && <text x="68" y="501" fontSize="32" fill={GOLD}>世界再透明，你也可以不打开</text>}
					{frame < 420 && <text x="68" y="551" fontSize="30" fill={SILVER}>未来 SI 思想实验</text>}
				</g>}

				{cover && <g>
					<rect x="48" y="342" width="400" height="174" fill="#060709" opacity="0.78"/>
					<text x="67" y="411" fontSize="58" fontWeight="600" letterSpacing="1.5" fill={IVORY}>
						世界再透明
					</text>
					<text x="67" y="483" fontSize="49" fontWeight="600" letterSpacing="0.5" fill={GOLD}>
						你也可以不打开
					</text>
				</g>}

				{!cover && lines.map((line, index) => (
					<text
						key={`${frame}-${index}`}
						x="485"
						y={1397 + index * 56}
						textAnchor="middle"
						fontFamily={'"PingFang SC", sans-serif'}
						fontSize="44"
						fontWeight="600"
						fill={CAPTION}
					>
						{line}
					</text>
				))}

				{!cover && frame >= 5010 && <g opacity={stamp}>
					<text x="65" y="548" fontSize="41" letterSpacing="2" fill={GOLD}>一眼万年 · 全三季终</text>
					<text x="68" y="600" fontFamily="Menlo, monospace" fontSize="28" letterSpacing="1.2" fill={SILVER}>
						THE FINAL EPISODE · 18
					</text>
				</g>}
				{!cover && frame >= 5160 && <text x="65" y="710" fontSize="30" fill={IVORY} opacity={closing * 0.65}>
					科幻想象 · 心印为隐私与选择的隐喻
				</text>}
			</svg>
			{!silent && <Audio src={staticFile('audio/master.wav')}/>}
		</AbsoluteFill>
	);
};

export default Film;
