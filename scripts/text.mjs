// Captions preserve the public-domain original; narration fixes only homophones.
export const passages = [
  ['date', 'landscape', '兰亭 · 雅集', ['暮春之初'], 'joy', '永和九年，岁在癸丑，暮春之初，会于会稽山阴之兰亭，修禊事也。'],
  ['grove', 'gathering', '兰亭 · 雅集', ['群贤毕至', '少长咸集'], 'joy', '群贤毕至，少长咸集。此地有崇山峻岭，茂林修竹。'],
  ['water', 'stream', '兰亭 · 雅集', ['清流激湍'], 'joy', '又有清流激湍，映带左右。'],
  ['cups', 'gathering', '兰亭 · 雅集', ['流觞曲水'], 'joy', '引以为流觞曲水，列坐其次。'],
  ['poems', 'gathering', '兰亭 · 雅集', ['一觞一咏'], 'joy', '虽无丝竹管弦之盛，一觞一咏，亦足以畅叙幽情。'],
  ['breeze', 'landscape', '兰亭 · 雅集', ['天朗气清', '惠风和畅'], 'joy', '是日也，天朗气清，惠风和畅。'],
  ['joy', 'landscape', '兰亭 · 雅集', ['信可乐也'], 'joy', '仰观宇宙之大，俯察品类之盛，所以游目骋怀，足以极视听之娱，信可乐也。'],
  ['life', 'study', '俯仰 · 一世', ['俯仰一世'], 'turn', '夫人之相与，俯仰一世，或取诸怀抱，悟言一室之内；或因寄所托，放浪形骸之外。'],
  ['contentment', 'gathering', '俯仰 · 一世', [], 'turn', '虽趣舍万殊，静躁不同，当其欣于所遇，暂得于己，快然自足，不知老之将至。'],
  ['change', 'stream', '俯仰 · 一世', ['情随事迁'], 'turn', '及其所之既倦，情随事迁，感慨系之矣。'],
  ['traces', 'landscape', '俯仰 · 一世', ['已为陈迹'], 'turn', '向之所欣，俯仰之间，已为陈迹，犹不能不以之兴怀。'],
  ['mortality', 'stream', '俯仰 · 一世', ['死生亦大矣'], 'reflect', '况修短随化，终期于尽。古人云：“死生亦大矣。”岂不痛哉！'],
  ['reading', 'study', '后之 · 览者', [], 'reflect', '每览昔人兴感之由，若合一契，未尝不临文嗟悼，不能喻之于怀。'],
  ['judgment', 'study', '后之 · 览者', [], 'reflect', '固知一死生为虚诞，齐彭殇为妄作。'],
  ['time', 'landscape', '后之 · 览者', ['后之视今', '今之视昔'], 'reflect', '后之视今，亦犹今之视昔，悲夫！'],
  ['record', 'study', '后之 · 览者', ['录其所述'], 'reflect', '故列叙时人，录其所述，虽世殊事异，所以兴怀，其致一也。'],
  ['future', 'landscape', '后之 · 览者', ['亦将有感于斯文'], 'reflect', '后之览者，亦将有感于斯文。'],
].map(([id, image, chapter, hero, mood, text]) => ({id, image, chapter, hero, mood, text}));

export const spoken = (text) => text
  .replace('会稽', '快稽')
  .replace('修禊', '修细')
  .replace('少长咸集', '绍掌咸集')
  .replace('夫人之相与', '扶人之相与')
  .replace('悟言', '晤言')
  .replace('趣舍', '取舍')
  .replace('悲夫', '悲福');
