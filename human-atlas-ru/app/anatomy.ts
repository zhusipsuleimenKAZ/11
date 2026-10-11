export type SystemId = 'skeletal'|'muscular'|'arterial'|'venous'|'nervous'|'digestive'|'respiratory'|'urinary'|'reproductive'|'lymphatic'|'endocrine'|'integumentary'|'connective'|'sensory'|'cardiac';
export const SYSTEMS: {id:SystemId;name:string;latin:string;color:string;description:string}[] = [
 {id:'skeletal',name:'Скелет',latin:'Systema skeletale',color:'#e2d9ba',description:'Кости образуют опорный каркас тела, защищают органы и служат местом прикрепления мышц. Костная ткань также депонирует минеральные вещества, а красный костный мозг образует клетки крови.'},
 {id:'muscular',name:'Мышцы',latin:'Systema musculare',color:'#a85b50',description:'Скелетные мышцы создают движение, натягивая места своего прикрепления. Вместе с сухожилиями они двигают суставы, поддерживают позу и вырабатывают тепло.'},
 {id:'cardiac',name:'Сердце',latin:'Cor',color:'#b96760',description:'Сердце — мышечный насос из четырёх камер. Его клапаны направляют кровь в одну сторону по малому и большому кругам кровообращения.'},
 {id:'sensory',name:'Органы чувств',latin:'Organa sensuum',color:'#b0c8ce',description:'Эти структуры обеспечивают специальные виды чувствительности: зрение, слух и равновесие. Их специализированные ткани воспринимают раздражители и передают информацию в нервную систему.'},
 {id:'arterial',name:'Артерии',latin:'Arteriae',color:'#c05245',description:'Сердце прогоняет кровь по сосудам. Артерии несут кровь от сердца к тканям, а в малом круге — к лёгким.'},
 {id:'venous',name:'Вены',latin:'Venae',color:'#527c9f',description:'Вены возвращают кровь к сердцу. Поверхностные и глубокие вены собирают кровь от тканей, а лёгочные вены приносят обогащённую кислородом кровь от лёгких.'},
 {id:'nervous',name:'Нервная',latin:'Systema nervosum',color:'#d8b565',description:'Головной и спинной мозг и периферические нервы проводят и обрабатывают сигналы. Они обеспечивают чувствительность, движения, координацию и автоматическую регуляцию функций организма.'},
 {id:'respiratory',name:'Дыхательная',latin:'Systema respiratorium',color:'#b98991',description:'Дыхательные пути проводят воздух к лёгким, где происходит обмен кислорода и углекислого газа между воздухом и кровью. Дыхание обеспечивается изменением давления, которое создают дыхательные мышцы.'},
 {id:'digestive',name:'Пищеварительная',latin:'Systema digestorium',color:'#b8916b',description:'Пищеварительный тракт расщепляет пищу, всасывает питательные вещества и воду и продвигает остатки дальше. Печень и поджелудочная железа выделяют жёлчь и пищеварительные ферменты.'},
 {id:'urinary',name:'Мочевая',latin:'Systema urinarium',color:'#b47961',description:'Почки фильтруют кровь и регулируют водный, электролитный и кислотно-щелочной баланс. Моча по мочеточникам поступает в мочевой пузырь и выводится через мочеиспускательный канал.'},
 {id:'lymphatic',name:'Лимфатическая',latin:'Systema lymphoideum',color:'#879f7c',description:'Лимфатические сосуды возвращают избыток тканевой жидкости в кровоток. Лимфатические узлы и другие лимфоидные органы участвуют в иммунном надзоре и иммунных реакциях.'},
 {id:'endocrine',name:'Эндокринная',latin:'Glandulae endocrinae',color:'#c5a09a',description:'Эндокринные органы выделяют гормоны в кровь и согласуют обмен веществ, рост, реакцию на стресс и размножение.'},
 {id:'reproductive',name:'Половая',latin:'Systema genitale masculinum',color:'#bda098',description:'Представленные мужские половые органы обеспечивают образование, созревание и транспорт сперматозоидов, а также выработку половых гормонов.'},
 {id:'integumentary',name:'Поверхность тела',latin:'Integumentum commune',color:'#ba9b7d',description:'Поверхность тела служит внешним анатомическим ориентиром. Покровная система образует защитный барьер и участвует в чувствительности и терморегуляции.'},
 {id:'connective',name:'Хрящи и связки',latin:'Textus connectivus',color:'#aec3bb',description:'Хрящи, связки и другие соединительные ткани поддерживают, соединяют и разделяют структуры. Они стабилизируют суставы и распределяют механическую нагрузку.'},
];
export interface Part {id:string;name:string;conceptId:string;system:SystemId;chunk:number;positions:number;normals:number;indices:number;vertexCount:number;indexCount:number;bounds:[number[],number[]]}
export interface Concept {id:string;name:string;elements:string[]}
export interface Atlas {version:string;sex?:'male';source?:string;scope?:string;parts:Part[];concepts:Concept[];chunks:{url:string;bytes:number;gzip?:string;gzipBytes?:number}[];triangles:number}
export type View = 'three-quarter'|'front'|'back'|'side';
export interface SceneState {inspectorOpen?:boolean;explode:number;visible:SystemId[];selected:string[];isolate:boolean;view:View;rotate:boolean;reset:number}
export const DEFAULT_VISIBLE:SystemId[] = ['cardiac','sensory','skeletal','muscular','arterial','venous','nervous','respiratory','digestive','urinary','lymphatic','endocrine','reproductive','connective'];
export const EXPLANATIONS:Record<string,string> = {
 'heart':'Мышечный насос в грудной полости. Правая половина сердца направляет кровь в лёгкие, левая — в большой круг кровообращения.',
 'liver':'Крупный орган под правым куполом диафрагмы. Перерабатывает всосавшиеся питательные вещества, вырабатывает жёлчь и синтезирует многие белки плазмы крови.',
 'brain':'Центральный орган нервной системы. Его взаимосвязанные отделы обеспечивают восприятие, движения, память, речь и регуляцию функций организма.',
 'stomach':'Мышечный полый орган между пищеводом и тонкой кишкой. Накапливает пищу и перемешивает её с кислотой и ферментами, а затем порциями передаёт в двенадцатиперстную кишку.',
 'spleen':'Лимфоидный орган в левом подреберье. Фильтрует кровь, удаляет стареющие клетки крови и участвует в иммунных реакциях.',
 'pancreas':'Орган брюшной полости с пищеварительной и эндокринной функциями. Выделяет ферменты в тонкую кишку и гормоны, в том числе инсулин и глюкагон.',
 'urinary bladder':'Мышечный резервуар в полости таза, в котором накапливается моча, поступающая из почек по мочеточникам.',
 'trachea':'Главный дыхательный путь между гортанью и бронхами. Хрящевые полукольца не дают ей спадаться при дыхании.',
 'diaphragm':'Широкая мышца, разделяющая грудную и брюшную полости. Сокращаясь, увеличивает объём грудной клетки и обеспечивает вдох.',
};
export function explanation(name:string,system:SystemId){return EXPLANATIONS[name.toLowerCase()] ?? SYSTEMS.find(s=>s.id===system)?.description ?? '';}
