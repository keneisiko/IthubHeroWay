import React, {useState} from "react";
export default (props) => {
	const [input1, onChangeInput1] = useState('');
	return (
		<div className="flex flex-col bg-white">
			<div className="self-stretch bg-neutral-100">
				<div className="flex flex-col items-center self-stretch pt-[26px]">
					<div className="flex items-center bg-[#9A33F4] py-[11px] mb-[30px] rounded-3xl" 
						style={{
							boxShadow: "25px 25px 20px #00000070"
						}}>
						<div className="flex shrink-0 items-center mr-[566px] gap-[3px]">
							<img
								src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/hfykh87w_expires_30_days.png"} 
								className="w-[167px] h-[60px] object-fill"
							/>
							<span className="text-neutral-100 text-[28px] font-bold" >
								{"Путь героя"}
							</span>
						</div>
						<div className="flex shrink-0 items-center mr-[17px] gap-2.5">
							<div className="flex flex-col shrink-0 items-start">
								<span className="text-white text-[22px] font-bold" >
									{"Имя пользователя"}
								</span>
								<div className="flex items-center ml-[73px]">
									<span className="text-[#FFD800] text-xl mr-[9px]" >
										{"Money:"}
									</span>
									<span className="text-[#FFD800] text-xl font-bold mr-2" >
										{"9.99"}
									</span>
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/c77omywh_expires_30_days.png"} 
										className="w-[18px] h-[18px] object-fill"
									/>
								</div>
							</div>
							<img
								src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/qq5pxpud_expires_30_days.png"} 
								className="w-12 h-12 object-fill"
							/>
						</div>
					</div>
					<div className="flex items-start mb-[3px] gap-5">
						<div className="flex flex-col shrink-0 items-start gap-[35px]">
							<div className="flex flex-col items-start bg-[#9A33F4] p-5 gap-6 rounded-3xl" 
								style={{
									boxShadow: "25px 25px 20px #00000070"
								}}>
								<div className="flex items-center gap-4">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/9i8ed54o_expires_30_days.png"} 
										className="w-[90px] h-[90px] object-fill"
									/>
									<div className="flex flex-col shrink-0 items-start gap-1">
										<button className="flex flex-col items-start bg-[#121212] text-left py-2 px-[151px] rounded-xl border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-[28px] font-bold" >
												{"Никнейм"}
											</span>
										</button>
										<button className="flex flex-col items-start bg-neutral-100 text-left py-1 px-4 mr-[339px] rounded-xl border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-[#121212] text-2xl font-bold" >
												{"ФИО"}
											</span>
										</button>
									</div>
								</div>
								<div className="flex flex-col items-start gap-1">
									<div className="flex items-center py-1">
										<span className="text-neutral-100 text-[22px] font-bold mr-2.5" >
											{"Трек:"}
										</span>
										<button className="flex flex-col shrink-0 items-start bg-[#121212] text-left py-1 px-4 mr-[137px] rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-[22px] font-bold" >
												{"Код - программирование"}
											</span>
										</button>
									</div>
									<div className="flex items-center py-1">
										<span className="text-neutral-100 text-[22px] font-bold mr-[11px]" >
											{"Отряд:"}
										</span>
										<button className="flex flex-col shrink-0 items-start bg-neutral-100 text-left py-1 px-4 mr-[233px] rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-[#121212] text-[22px] font-bold" >
												{"Учебная группа"}
											</span>
										</button>
									</div>
									<div className="flex items-center py-1">
										<span className="text-neutral-100 text-[22px] font-bold mr-[11px]" >
											{"Статус и уровень:"}
										</span>
										<button className="flex flex-col shrink-0 items-start bg-[#121212] text-left py-1 px-4 mr-[145px] rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-[22px] font-bold" >
												{"Стажёр ур. 3"}
											</span>
										</button>
									</div>
								</div>
							</div>
							<div className="flex flex-col items-start relative">
								<div className="flex flex-col items-start bg-neutral-100 py-5 rounded-3xl" 
									style={{
										boxShadow: "25px 25px 20px #00000070"
									}}>
									<span className="text-[#9A33F4] text-[28px] font-bold mb-7 ml-5" >
										{"Карта пути:"}
									</span>
									<div className="flex items-start relative mb-1.5 mx-[26px]">
										<img
											src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/sd1y0oqh_expires_30_days.png"} 
											className="w-[30px] h-[30px] mr-1 object-fill"
										/>
										<div className="flex flex-col shrink-0 items-start pb-3">
											<img
												src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/v4dpxuw8_expires_30_days.png"} 
												className="w-[30px] h-[30px] ml-[101px] object-fill"
											/>
											<img
												src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/6gms41nb_expires_30_days.png"} 
												className="w-[30px] h-[30px] ml-[236px] object-fill"
											/>
											<div className="bg-[#9A33F4] w-[97px] h-1.5 rounded-lg">
											</div>
											<div className="bg-[#9A33F4] w-[97px] h-1.5 ml-[135px] rounded-lg">
											</div>
											<div className="bg-[#848484] w-[97px] h-1.5 ml-[270px] rounded-lg">
											</div>
											<div className="flex flex-col items-start bg-neutral-100 py-5 pl-3 pr-[38px] ml-[298px] gap-2.5 rounded-xl border-4 border-solid border-[#9A33F4]" 
												style={{
													boxShadow: "25px 25px 20px #00000070"
												}}>
												<span className="text-[#121212] text-base font-bold" >
													{"Описание"}
												</span>
												<span className="text-[#121212] text-[15px] w-[126px]" >
													{"Дата прохождения:"}
												</span>
											</div>
											<div className="bg-[#848484] w-[81px] h-1.5 mb-[18px] ml-[405px] rounded-lg">
											</div>
											<span className="text-[#9A33F4] text-base font-bold text-center w-[60px] ml-[84px]" >
												{"Первая\nпобеда"}
											</span>
											<span className="text-[#9A33F4] text-xl font-bold text-center w-[82px] mb-[17px] ml-52" >
												{"Первый\nпровал"}
											</span>
											<img
												src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/1rbz1w3h_expires_30_days.png"} 
												className="w-[30px] h-[30px] ml-[55px] object-fill"
											/>
											<img
												src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/zz44330w_expires_30_days.png"} 
												className="w-[30px] h-[30px] ml-[190px] object-fill"
											/>
											<div className="bg-[#848484] w-[97px] h-1.5 ml-[89px] rounded-lg">
											</div>
											<div className="bg-[#848484] w-[97px] h-1.5 ml-56 rounded-lg">
											</div>
										</div>
										<img
											src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/za843jst_expires_30_days.png"} 
											className="w-[30px] h-[30px] absolute bottom-0 right-[131px] object-fill"
										/>
										<img
											src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/zdofq39t_expires_30_days.png"} 
											className="w-[30px] h-[30px] absolute top-0 right-[85px] object-fill"
										/>
									</div>
									<div className="flex items-center ml-[93px]">
										<span className="text-[#848484] text-base font-bold mr-12" >
											{"Продукт"}
										</span>
										<span className="text-[#848484] text-base font-bold mr-[52px]" >
											{"Стажировка"}
										</span>
										<span className="text-[#848484] text-base font-bold" >
											{"Выпуск"}
										</span>
									</div>
								</div>
								<div className="flex flex-col items-start bg-[#9A33F4] absolute bottom-[30px] left-[-47px] py-5 pl-3 pr-[38px] gap-2.5 rounded-xl" 
									style={{
										boxShadow: "25px 25px 20px #00000070"
									}}>
									<span className="text-neutral-100 text-base font-bold" >
										{"Описание"}
									</span>
									<span className="text-neutral-100 text-[15px] w-[126px]" >
										{"Дата прохождения:"}
									</span>
								</div>
							</div>
						</div>
						<div className="flex flex-col shrink-0 items-start bg-neutral-100 pt-5 pl-5 pr-1.5 rounded-3xl" 
							style={{
								boxShadow: "25px 25px 20px #00000070"
							}}>
							<div className="flex flex-col items-start mb-5">
								<button className="flex flex-col items-start bg-[#121212] text-left py-[17px] px-5 mb-5 mr-[118px] rounded-2xl border-4 border-solid border-neutral-100" 
									style={{
										boxShadow: "25px 25px 20px #00000070"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-neutral-100 text-2xl font-bold" >
										{"Настроить профиль"}
									</span>
								</button>
								<div className="bg-[#9A33F4] w-[420px] h-1 mb-4">
								</div>
								<div className="flex flex-col items-start gap-3">
									<span className="text-[#9A33F4] text-[28px] font-bold mr-[248px]" >
										{"Статистика:"}
									</span>
									<div className="flex flex-col items-start pr-[59px] gap-3">
										<button className="flex flex-col items-start bg-[#9A33F4] text-left py-1 px-4 rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-[22px] font-bold" >
												{"Выполнено квестов: 47"}
											</span>
										</button>
										<button className="flex flex-col items-start bg-[#9A33F4] text-left py-1 px-4 rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-[22px] font-bold" >
												{"Получено нашивок: 12 из 42"}
											</span>
										</button>
										<button className="flex flex-col items-start bg-[#9A33F4] text-left py-1 px-4 rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-[22px] font-bold" >
												{"Побед в дуелях: 5"}
											</span>
										</button>
									</div>
								</div>
							</div>
							<span className="text-[#9A33F4] text-[28px] font-bold mb-3" >
								{"Шефство:"}
							</span>
							<button className="flex flex-col items-start bg-neutral-100 text-left py-[5px] px-4 mb-2 rounded-[48px] border-4 border-solid border-[#121212]"
								onClick={()=>alert("Pressed!")}>
								<span className="text-[#9A33F4] text-xl font-bold" >
									{"@подшефный"}
								</span>
							</button>
							<button className="flex flex-col items-start bg-[#121212] text-left py-[9px] px-5 mb-5 rounded-[48px] border-4 border-solid border-neutral-100" 
								style={{
									boxShadow: "25px 25px 20px #00000070"
								}}
								onClick={()=>alert("Pressed!")}>
								<span className="text-neutral-100 text-2xl font-bold" >
									{"Стать наставником"}
								</span>
							</button>
							<div className="flex items-start mb-1.5 gap-[55px]">
								<div className="flex flex-col shrink-0 items-start gap-2">
									<button className="flex flex-col items-start bg-neutral-100 text-left py-[5px] px-4 mr-[93px] rounded-[48px] border-4 border-solid border-[#121212]"
										onClick={()=>alert("Pressed!")}>
										<span className="text-[#9A33F4] text-xl font-bold" >
											{"@подшефный2"}
										</span>
									</button>
									<button className="flex flex-col items-start bg-[#121212] text-left py-[9px] px-5 rounded-[48px] border-4 border-solid border-neutral-100" 
										style={{
											boxShadow: "25px 25px 20px #00000070"
										}}
										onClick={()=>alert("Pressed!")}>
										<span className="text-neutral-100 text-2xl font-bold" >
											{"Стать наставником"}
										</span>
									</button>
								</div>
								<img
									src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/wybv8q39_expires_30_days.png"} 
									className="w-[88px] h-[86px] mt-[19px] rounded-3xl object-fill"
								/>
							</div>
						</div>
						<div className="flex flex-col shrink-0 items-start relative mt-[25px]">
							<div className="flex flex-col items-start bg-neutral-100 py-11 rounded-3xl" 
								style={{
									boxShadow: "25px 25px 20px #00000070"
								}}>
								<div className="flex flex-col items-start mb-5">
									<div className="w-[100px] h-[52px] py-2.5 px-[33px]" 
										style={{
											background: "linear-gradient(180deg, #591D8E00, #9A33F4, #591D8E00)"
										}}>
									</div>
									<span className="text-[#9A33F4] text-base font-bold ml-[17px]" >
										{"Главная"}
									</span>
								</div>
								<img
									src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/dubit0vk_expires_30_days.png"} 
									className="w-[100px] h-[52px] object-fill"
								/>
								<span className="text-[#9A33F4] text-base font-bold mb-5 ml-3" >
									{"Профиль"}
								</span>
								<div className="flex flex-col items-start mb-5">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/rwrjowj7_expires_30_days.png"} 
										className="w-[100px] h-[52px] object-fill"
									/>
									<span className="text-[#9A33F4] text-base font-bold ml-5" >
										{"Квесты"}
									</span>
								</div>
								<div className="flex flex-col items-start mb-5">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/v1fr3a3a_expires_30_days.png"} 
										className="w-[100px] h-[52px] object-fill"
									/>
									<span className="text-[#9A33F4] text-base font-bold ml-[13px]" >
										{"Магазин"}
									</span>
								</div>
								<div className="flex flex-col items-start mb-5">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/n5xnhjqe_expires_30_days.png"} 
										className="w-[100px] h-[52px] object-fill"
									/>
									<span className="text-[#9A33F4] text-base font-bold ml-[15px]" >
										{"Лидеры"}
									</span>
								</div>
								<div className="flex flex-col items-start">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/srq2nznq_expires_30_days.png"} 
										className="w-[100px] h-[52px] object-fill"
									/>
									<span className="text-[#9A33F4] text-base font-bold ml-[17px]" >
										{"Отряды"}
									</span>
								</div>
							</div>
							<div className="bg-[#9A33F4] w-3.5 h-16 absolute top-[130px] right-[-7px] rounded" 
								style={{
									boxShadow: "5px 5px 17px #9A33F4"
								}}>
							</div>
						</div>
					</div>
					<div className="flex items-start mb-[9px] gap-[3px]">
						<div className="bg-[#9A33F4] w-[7px] h-[15px] mt-[15px] rounded-sm">
						</div>
						<div className="bg-[#9A33F4] w-[7px] h-[30px] rounded-sm">
						</div>
						<div className="bg-[#9A33F4] w-[7px] h-[22px] mt-2 rounded-sm">
						</div>
					</div>
					<span className="text-[#9A33F4] text-2xl font-bold mb-[11px]" >
						{"Мощность"}
					</span>
					<div className="flex items-start mb-[33px]">
						<div className="flex flex-col shrink-0 items-start mt-[219px] mr-14">
							<div className="flex items-start ml-[23px] gap-[3px]">
								<div className="bg-[#9A33F4] w-[7px] h-[15px] mt-[15px] rounded-sm">
								</div>
								<div className="bg-[#9A33F4] w-[7px] h-[30px] rounded-sm">
								</div>
								<div className="bg-[#9A33F4] w-[7px] h-[22px] mt-2 rounded-sm">
								</div>
							</div>
							<span className="text-[#9A33F4] text-2xl font-bold" >
								{"Связь"}
							</span>
						</div>
						<div className="flex flex-col shrink-0 items-start relative mt-[17px] mr-[53px]">
							<div className="flex flex-col items-start relative">
								<div className="flex flex-col items-start bg-cover bg-center pt-16 px-[119px]"
									style={{
										backgroundImage: 'url(https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/u33zmsfa_expires_30_days.png)',
									}}
									>
									<div className="flex flex-col items-start relative mb-36">
										<div className="flex flex-col items-start relative">
											<div className="flex flex-col items-start bg-cover bg-center pt-[350px] pl-[243px] pr-[121px]"
												style={{
													backgroundImage: 'url(https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/vikmlfz9_expires_30_days.png)',
												}}
												>
												<button className="flex flex-col items-start bg-neutral-100 text-left py-1 px-4 mb-1.5 rounded-[48px] border-0" 
													style={{
														boxShadow: "4px 4px 7px #00000040"
													}}
													onClick={()=>alert("Pressed!")}>
													<span className="text-[#121212] text-[22px] font-bold" >
														{"14"}
													</span>
												</button>
											</div>
											<button className="flex flex-col items-start bg-neutral-100 text-left absolute bottom-[172px] right-[-17px] py-1 px-4 rounded-[48px] border-0" 
												style={{
													boxShadow: "4px 4px 7px #00000040"
												}}
												onClick={()=>alert("Pressed!")}>
												<span className="text-[#121212] text-[22px] font-bold" >
													{"14"}
												</span>
											</button>
											<button className="flex flex-col items-start bg-neutral-100 text-left absolute bottom-[166px] left-[-19px] py-1 px-4 rounded-[48px] border-0" 
												style={{
													boxShadow: "4px 4px 7px #00000040"
												}}
												onClick={()=>alert("Pressed!")}>
												<span className="text-[#121212] text-[22px] font-bold" >
													{"14"}
												</span>
											</button>
											<button className="flex flex-col items-start bg-neutral-100 text-left absolute bottom-[-19px] left-[75px] py-1 px-4 rounded-[48px] border-0" 
												style={{
													boxShadow: "4px 4px 7px #00000040"
												}}
												onClick={()=>alert("Pressed!")}>
												<span className="text-[#121212] text-[22px] font-bold" >
													{"14"}
												</span>
											</button>
										</div>
										<div className="flex flex-col items-center self-stretch absolute top-[-16px] right-0 left-0">
											<button className="flex flex-col items-start bg-neutral-100 text-left py-1 px-4 rounded-[48px] border-0" 
												style={{
													boxShadow: "4px 4px 7px #00000040"
												}}
												onClick={()=>alert("Pressed!")}>
												<span className="text-[#121212] text-[22px] font-bold" >
													{"14"}
												</span>
											</button>
										</div>
									</div>
								</div>
								<button className="flex flex-col items-start bg-[#9A33F4] text-left absolute top-[223px] left-[-27px] py-1 px-4 rounded-[48px] border-0" 
									style={{
										boxShadow: "4px 4px 7px #00000040"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-neutral-100 text-[22px] font-bold" >
										{"17"}
									</span>
								</button>
								<button className="flex flex-col items-start bg-[#9A33F4] text-left absolute top-[223px] right-[-27px] py-1 px-4 rounded-[48px] border-0" 
									style={{
										boxShadow: "4px 4px 7px #00000040"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-neutral-100 text-[22px] font-bold" >
										{"17"}
									</span>
								</button>
								<button className="flex flex-col items-start bg-[#9A33F4] text-left absolute bottom-[18px] left-[-266px] py-5 px-7 rounded-xl border-0" 
									style={{
										boxShadow: "25px 25px 20px #00000070"
									}}
									onClick={()=>alert("Pressed!")}>
									<div className="flex flex-col items-start gap-6">
										<span className="text-neutral-100 text-xl font-bold mr-[140px]" >
											{"История"}
										</span>
										<div className="flex flex-col items-start">
											<div className="flex items-center gap-2.5">
												<div className="flex flex-col shrink-0 items-start gap-[13px]">
													<span className="text-white text-base font-bold" >
														{"20"}
													</span>
													<span className="text-white text-base font-bold" >
														{"15"}
													</span>
													<span className="text-white text-base font-bold" >
														{"10"}
													</span>
													<span className="text-white text-base font-bold" >
														{"5"}
													</span>
													<span className="text-white text-base font-bold" >
														{"0"}
													</span>
												</div>
												<div className="flex flex-col shrink-0 items-start pt-[7px] pb-4 px-2 rounded border-4 border-solid border-neutral-100">
													<div className="bg-white w-[188px] h-[1px] mb-2">
													</div>
													<div className="bg-white w-[188px] h-[1px] mb-2">
													</div>
													<div className="bg-white w-[188px] h-[1px]">
													</div>
													<div className="items-start pb-2">
														<div className="w-[162px] h-[98px] rounded border-4 border-solid border-neutral-100">
														</div>
														<div className="bg-white w-[188px] h-[1px] mb-2">
														</div>
														<div className="bg-white w-[188px] h-[1px] mb-2">
														</div>
														<div className="bg-white w-[188px] h-[1px] mb-2">
														</div>
														<div className="bg-white w-[188px] h-[1px] mb-2">
														</div>
														<div className="bg-white w-[188px] h-[1px] mb-2">
														</div>
														<div className="bg-white w-[188px] h-[1px] mb-2">
														</div>
														<div className="bg-white w-[188px] h-[1px] mb-2">
														</div>
														<div className="bg-white w-[188px] h-[1px] mb-2">
														</div>
														<div className="bg-white w-[188px] h-[1px] mb-2">
														</div>
														<div className="bg-white w-[188px] h-[1px]">
														</div>
													</div>
													<div className="bg-white w-[188px] h-[1px]">
													</div>
												</div>
											</div>
											<div className="flex flex-col items-center ml-[33px] gap-1">
												<div className="flex items-center">
													<span className="text-white text-base font-bold mr-[30px]" >
														{"1"}
													</span>
													<span className="text-white text-base font-bold mr-[29px]" >
														{"2"}
													</span>
													<span className="text-white text-base font-bold mr-[29px]" >
														{"3"}
													</span>
													<span className="text-white text-base font-bold mr-7" >
														{"4"}
													</span>
													<span className="text-white text-base font-bold mr-[29px]" >
														{"5"}
													</span>
													<span className="text-white text-base font-bold" >
														{"6"}
													</span>
												</div>
												<span className="text-white text-base font-bold" >
													{"Недели"}
												</span>
											</div>
										</div>
									</div>
								</button>
								<button className="flex flex-col items-start bg-[#9A33F4] text-left absolute bottom-[-17px] left-[102px] py-1 px-4 rounded-[48px] border-0" 
									style={{
										boxShadow: "4px 4px 7px #00000040"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-neutral-100 text-[22px] font-bold" >
										{"17"}
									</span>
								</button>
								<button className="flex flex-col items-start bg-[#9A33F4] text-left absolute bottom-[-17px] right-[101px] py-1 px-4 rounded-[48px] border-0" 
									style={{
										boxShadow: "4px 4px 7px #00000040"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-neutral-100 text-[22px] font-bold" >
										{"17"}
									</span>
								</button>
							</div>
							<div className="flex flex-col items-center self-stretch absolute top-[-17px] right-0 left-0">
								<button className="flex flex-col items-start bg-[#9A33F4] text-left py-1 px-4 rounded-[48px] border-0" 
									style={{
										boxShadow: "4px 4px 7px #00000040"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-neutral-100 text-[22px] font-bold" >
										{"17"}
									</span>
								</button>
							</div>
						</div>
						<div className="flex flex-col shrink-0 items-start mt-52 gap-[9px]">
							<div className="flex items-start ml-[29px] gap-[3px]">
								<div className="bg-[#9A33F4] w-[7px] h-[15px] mt-[15px] rounded-sm">
								</div>
								<div className="bg-[#9A33F4] w-[7px] h-[30px] rounded-sm">
								</div>
								<div className="bg-[#9A33F4] w-[7px] h-[22px] mt-2 rounded-sm">
								</div>
							</div>
							<span className="text-[#9A33F4] text-2xl font-bold" >
								{"Фокус"}
							</span>
						</div>
					</div>
					<div className="flex items-center mb-[9px]">
						<div className="flex shrink-0 items-start mr-[393px] gap-[3px]">
							<div className="bg-[#9A33F4] w-[7px] h-[15px] mt-[15px] rounded-sm">
							</div>
							<div className="bg-[#9A33F4] w-[7px] h-[30px] rounded-sm">
							</div>
							<div className="bg-[#9A33F4] w-[7px] h-[22px] mt-2 rounded-sm">
							</div>
						</div>
						<div className="flex shrink-0 items-start gap-[3px]">
							<div className="bg-[#9A33F4] w-[7px] h-[15px] mt-[15px] rounded-sm">
							</div>
							<div className="bg-[#9A33F4] w-[7px] h-[30px] rounded-sm">
							</div>
							<div className="bg-[#9A33F4] w-[7px] h-[22px] mt-2 rounded-sm">
							</div>
						</div>
					</div>
					<div className="flex items-center mb-[52px]">
						<span className="text-[#9A33F4] text-2xl font-bold mr-[345px]" >
							{"Ритм"}
						</span>
						<span className="text-[#9A33F4] text-2xl font-bold" >
							{"Отдача"}
						</span>
					</div>
					<div className="flex flex-col items-start bg-neutral-100 p-11 mb-12 gap-14 rounded-3xl border-4 border-solid border-[#9A33F4]" 
						style={{
							boxShadow: "25px 25px 20px #00000070"
						}}>
						<div className="flex flex-col items-center gap-8">
							<span className="text-[#9A33F4] text-[28px] font-bold" >
								{"Достижения:"}
							</span>
							<div className="flex items-center px-[280px] gap-12">
								<div className="flex flex-col shrink-0 items-start gap-2">
									<button className="flex flex-col items-start bg-neutral-100 text-left p-[31px] ml-[15px] rounded-xl border-4 border-solid border-[#9A33F4]" 
										style={{
											boxShadow: "25px 25px 20px #00000070"
										}}
										onClick={()=>alert("Pressed!")}>
										<div className="items-start p-[19px] border-[9px] border-solid border-[#9A33F4]">
											<div className="bg-[#9A33F4] w-[15px] h-[15px]">
											</div>
										</div>
									</button>
									<div className="flex flex-col items-center px-[21px] gap-1">
										<span className="text-[#121212] text-xl font-bold" >
											{"Название"}
										</span>
										<button className="flex flex-col items-start bg-[#121212] text-left py-1 px-3 rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-base font-bold" >
												{"Редкость"}
											</span>
										</button>
									</div>
								</div>
								<div className="flex flex-col shrink-0 items-start gap-2">
									<button className="flex flex-col items-start bg-neutral-100 text-left p-[31px] ml-[15px] rounded-xl border-4 border-solid border-[#9A33F4]" 
										style={{
											boxShadow: "25px 25px 20px #00000070"
										}}
										onClick={()=>alert("Pressed!")}>
										<div className="items-start p-[19px] border-[9px] border-solid border-[#9A33F4]">
											<div className="bg-[#9A33F4] w-[15px] h-[15px]">
											</div>
										</div>
									</button>
									<div className="flex flex-col items-center px-[21px] gap-1">
										<span className="text-[#121212] text-xl font-bold" >
											{"Название"}
										</span>
										<button className="flex flex-col items-start bg-[#121212] text-left py-1 px-3 rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-base font-bold" >
												{"Редкость"}
											</span>
										</button>
									</div>
								</div>
								<div className="flex flex-col shrink-0 items-start gap-2">
									<button className="flex flex-col items-start bg-neutral-100 text-left p-[31px] ml-[15px] rounded-xl border-4 border-solid border-[#9A33F4]" 
										style={{
											boxShadow: "25px 25px 20px #00000070"
										}}
										onClick={()=>alert("Pressed!")}>
										<div className="items-start p-[19px] border-[9px] border-solid border-[#9A33F4]">
											<div className="bg-[#9A33F4] w-[15px] h-[15px]">
											</div>
										</div>
									</button>
									<div className="flex flex-col items-center px-[21px] gap-1">
										<span className="text-[#121212] text-xl font-bold" >
											{"Название"}
										</span>
										<button className="flex flex-col items-start bg-[#121212] text-left py-1 px-3 rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-base font-bold" >
												{"Редкость"}
											</span>
										</button>
									</div>
								</div>
							</div>
						</div>
						<div className="flex flex-col items-start gap-10">
							<div className="flex flex-col items-start gap-2">
								<div className="flex items-center px-[42px]">
									<span className="text-[#9A33F4] text-[28px] font-bold mr-[52px]" >
										{"Путь"}
									</span>
									<span className="text-[#848484] text-2xl font-bold mr-[53px]" >
										{"Ритм"}
									</span>
									<span className="text-[#848484] text-2xl font-bold mr-[52px]" >
										{"Мастерство"}
									</span>
									<span className="text-[#848484] text-2xl font-bold mr-[50px]" >
										{"Сообщество"}
									</span>
									<span className="text-[#848484] text-2xl font-bold mr-[52px]" >
										{"Вклад"}
									</span>
									<span className="text-[#848484] text-2xl font-bold mr-[50px]" >
										{"Статус"}
									</span>
									<span className="text-[#848484] text-2xl font-bold" >
										{"Особые"}
									</span>
								</div>
								<div className="items-start relative pl-[31px] pr-[974px] ml-[11px]">
									<div className="bg-[#9A33F4] w-[65px] h-3.5 rounded" 
										style={{
											boxShadow: "5px 5px 17px #9A33F4"
										}}>
									</div>
									<div className="self-stretch bg-[#9A33F4] h-1 absolute bottom-[1px] right-0 left-0">
									</div>
								</div>
							</div>
							<div className="flex flex-col items-center px-3.5 gap-8">
								<div className="flex items-start">
									<div className="flex flex-col shrink-0 items-start mr-8 gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#9A33F4]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#9A33F4]">
												<div className="bg-[#9A33F4] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-start gap-1">
											<span className="text-[#121212] text-xl font-bold" >
												{"Название"}
											</span>
											<button className="flex flex-col items-start bg-[#121212] text-left py-1 px-[11px] rounded-[48px] border-0"
												onClick={()=>alert("Pressed!")}>
												<span className="text-[#9A33F4] text-base font-bold" >
													{"Обычный"}
												</span>
											</button>
										</div>
									</div>
									<div className="flex flex-col shrink-0 items-start mr-6 gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#38DDDD]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#9A33F4]">
												<div className="bg-[#9A33F4] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-center px-0.5 gap-1">
											<span className="text-[#121212] text-xl font-bold" >
												{"Название"}
											</span>
											<button className="flex flex-col items-start bg-[#121212] text-left py-1 px-3 rounded-[48px] border-0"
												onClick={()=>alert("Pressed!")}>
												<span className="text-[#38DDDD] text-base font-bold" >
													{"Редкий"}
												</span>
											</button>
										</div>
									</div>
									<div className="flex flex-col shrink-0 items-start mr-3.5">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 mb-2 ml-[15px] rounded-xl border-4 border-solid border-[#FF00EE]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#9A33F4]">
												<div className="bg-[#9A33F4] w-3 h-3">
												</div>
											</div>
										</button>
										<span className="text-[#121212] text-xl font-bold mb-1 ml-2.5" >
											{"Название"}
										</span>
										<input
											placeholder={"Эпический"}
											value={input1}
											onChange={(event)=>onChangeInput1(event.target.value)}
											className="text-[#FF00EE] bg-[#121212] text-base font-bold py-1 px-3 rounded-[48px] border-0"
										/>
									</div>
									<div className="flex flex-col shrink-0 items-start mr-[33px]">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 mb-2 ml-[26px] rounded-xl border-4 border-solid border-[#FFD900]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#9A33F4]">
												<div className="bg-[#9A33F4] w-3 h-3">
												</div>
											</div>
										</button>
										<span className="text-[#121212] text-xl font-bold mb-1 ml-[21px]" >
											{"Название"}
										</span>
										<div className="flex flex-col items-start relative">
											<div className="bg-[#121212] w-[105px] h-7 rounded-[48px]">
											</div>
											<span className="text-[#FFD900] text-base font-bold absolute top-1 left-3" >
												{"Легендарный"}
											</span>
										</div>
									</div>
									<div className="flex flex-col shrink-0 items-start mr-8 gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#848484]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#B1B1B1]">
												<div className="bg-[#B1B1B1] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-start px-1">
											<span className="text-[#848484] text-base font-bold text-center w-24" >
												{"Условие не выполнено"}
											</span>
										</div>
									</div>
									<div className="flex flex-col shrink-0 items-start mr-8 gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#848484]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#B1B1B1]">
												<div className="bg-[#B1B1B1] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-start px-1">
											<span className="text-[#848484] text-base font-bold text-center w-24" >
												{"Условие не выполнено"}
											</span>
										</div>
									</div>
									<div className="flex flex-col shrink-0 items-start mr-8 gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#848484]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#B1B1B1]">
												<div className="bg-[#B1B1B1] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-start px-1">
											<span className="text-[#848484] text-base font-bold text-center w-24" >
												{"Условие не выполнено"}
											</span>
										</div>
									</div>
									<div className="flex flex-col shrink-0 items-start gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#848484]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#B1B1B1]">
												<div className="bg-[#B1B1B1] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-start px-1">
											<span className="text-[#848484] text-base font-bold text-center w-24" >
												{"Условие не выполнено"}
											</span>
										</div>
									</div>
								</div>
								<div className="flex items-center gap-8">
									<div className="flex flex-col shrink-0 items-start gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#848484]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#B1B1B1]">
												<div className="bg-[#B1B1B1] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-start px-1">
											<span className="text-[#848484] text-base font-bold text-center w-24" >
												{"Условие не выполнено"}
											</span>
										</div>
									</div>
									<div className="flex flex-col shrink-0 items-start gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#848484]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#B1B1B1]">
												<div className="bg-[#B1B1B1] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-start px-1">
											<span className="text-[#848484] text-base font-bold text-center w-24" >
												{"Условие не выполнено"}
											</span>
										</div>
									</div>
									<div className="flex flex-col shrink-0 items-start gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#848484]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#B1B1B1]">
												<div className="bg-[#B1B1B1] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-start px-1">
											<span className="text-[#848484] text-base font-bold text-center w-24" >
												{"Условие не выполнено"}
											</span>
										</div>
									</div>
									<div className="flex flex-col shrink-0 items-start gap-2">
										<button className="flex flex-col items-start bg-neutral-100 text-left p-6 rounded-xl border-4 border-solid border-[#848484]" 
											style={{
												boxShadow: "25px 25px 20px #00000070"
											}}
											onClick={()=>alert("Pressed!")}>
											<div className="items-start p-[15px] border-[9px] border-solid border-[#B1B1B1]">
												<div className="bg-[#B1B1B1] w-3 h-3">
												</div>
											</div>
										</button>
										<div className="flex flex-col items-start px-1">
											<span className="text-[#848484] text-base font-bold text-center w-24" >
												{"Условие не выполнено"}
											</span>
										</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	)
}