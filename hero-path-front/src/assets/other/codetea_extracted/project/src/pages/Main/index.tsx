import React from "react";
export default (props) => {
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
								src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/bfnbkn8u_expires_30_days.png"} 
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
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/5ziy1nif_expires_30_days.png"} 
										className="w-[18px] h-[18px] object-fill"
									/>
								</div>
							</div>
							<img
								src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/6ud0gzxn_expires_30_days.png"} 
								className="w-12 h-12 object-fill"
							/>
						</div>
					</div>
					<div className="flex items-start mb-[19px]">
						<div className="flex flex-col shrink-0 items-start mr-[77px] gap-5">
							<div className="flex flex-col items-start bg-neutral-100 p-5 gap-4 rounded-3xl" 
								style={{
									boxShadow: "25px 25px 20px #00000070"
								}}>
								<div className="flex items-center gap-[7px]">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/6q7lpkkk_expires_30_days.png"} 
										className="w-[132px] h-[133px] object-fill"
									/>
									<div className="flex flex-col shrink-0 items-start pr-[157px]">
										<span className="text-[#9A33F4] text-4xl font-bold" >
											{"Серия:"}
										</span>
										<span className="text-[#9A33F4] text-[28px] font-bold w-[162px]" >
											{"12 дней без опозданий"}
										</span>
									</div>
								</div>
								<div className="flex flex-col items-start gap-1">
									<div className="flex items-center">
										<span className="text-[#848484] text-[22px] font-bold mr-[255px]" >
											{"7 дней"}
										</span>
										<span className="text-[#121212] text-[22px] font-bold" >
											{"14 дней"}
										</span>
									</div>
									<div className="flex items-center gap-2">
										<img
											src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/tfrpjowd_expires_30_days.png"} 
											className="w-[30px] h-[30px] object-fill"
										/>
										<div className="shrink-0 items-start bg-[#121212] py-[3px] pl-[3px] pr-[90px] rounded-md">
											<div className="bg-neutral-100 w-[251px] h-1.5 rounded-[5px]">
											</div>
										</div>
										<img
											src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/av2pawb9_expires_30_days.png"} 
											className="w-[30px] h-[30px] object-fill"
										/>
									</div>
									<div className="flex items-center">
										<span className="text-[#848484] text-[22px] font-bold mr-[206px]" >
											{"+5 монет"}
										</span>
										<span className="text-[#9A33F4] text-[22px] font-bold" >
											{"+15 монет"}
										</span>
									</div>
								</div>
							</div>
							<div className="flex flex-col items-start bg-[#9A33F4] pt-5 pb-[21px] px-5 gap-4 rounded-3xl" 
								style={{
									boxShadow: "25px 25px 20px #00000070"
								}}>
								<div className="flex flex-col items-start gap-2">
									<span className="text-neutral-100 text-[28px] font-bold mr-[166px]" >
										{"Текущий рейтинг:"}
									</span>
									<button className="flex flex-col items-start bg-[#121212] text-left py-[3px] px-[177px] rounded-xl border-0"
										onClick={()=>alert("Pressed!")}>
										<span className="text-neutral-100 text-4xl font-bold" >
											{"199"}
										</span>
									</button>
								</div>
								<div className="flex items-center">
									<span className="text-neutral-100 text-2xl font-bold mr-[13px]" >
										{"Статус:"}
									</span>
									<button className="flex flex-col shrink-0 items-start bg-neutral-100 text-left py-[3px] px-4 mr-2.5 rounded-[48px] border-0"
										onClick={()=>alert("Pressed!")}>
										<span className="text-[#121212] text-2xl font-bold" >
											{"Игрок"}
										</span>
									</button>
									<button className="flex flex-col shrink-0 items-start bg-neutral-100 text-left py-[3px] px-4 mr-[103px] rounded-[48px] border-0"
										onClick={()=>alert("Pressed!")}>
										<span className="text-[#121212] text-2xl font-bold" >
											{"6 ур."}
										</span>
									</button>
								</div>
								<div className="flex flex-col items-start mr-[107px] gap-4">
									<div className="flex items-center">
										<span className="text-neutral-100 text-2xl font-bold mr-3.5" >
											{"до"}
										</span>
										<button className="flex flex-col shrink-0 items-start bg-[#121212] text-left py-[3px] px-4 mr-3 rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-2xl font-bold" >
												{"Лидера"}
											</span>
										</button>
										<span className="text-neutral-100 text-2xl font-bold" >
											{"осталось:"}
										</span>
									</div>
									<button className="flex flex-col items-start bg-neutral-100 text-left py-[3px] px-4 mr-[141px] rounded-[48px] border-0"
										onClick={()=>alert("Pressed!")}>
										<span className="text-[#121212] text-2xl font-bold" >
											{"150 баллов"}
										</span>
									</button>
								</div>
								<div className="flex items-center gap-2">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/2ujegf3a_expires_30_days.png"} 
										className="w-[30px] h-[30px] object-fill"
									/>
									<div className="shrink-0 items-start bg-[#121212] py-[3px] pl-[3px] pr-[90px] rounded-md">
										<div className="bg-neutral-100 w-[251px] h-1.5 rounded-[5px]">
										</div>
									</div>
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/18hq8ybc_expires_30_days.png"} 
										className="w-[30px] h-[30px] object-fill"
									/>
								</div>
								<div className="flex items-center">
									<span className="text-neutral-100 text-[22px] font-bold mr-[273px]" >
										{"Игрок"}
									</span>
									<span className="text-neutral-100 text-[22px] font-bold" >
										{"Лидер"}
									</span>
								</div>
							</div>
						</div>
						<div className="flex flex-col shrink-0 items-start relative p-[22px] mt-24 mr-[78px]">
							<div className="flex flex-col items-start relative">
								<img
									src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/rhlqjnu8_expires_30_days.png"} 
									className="w-[424px] h-[401px] object-fill"
								/>
								<img
									src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/uax43i41_expires_30_days.png"} 
									className="w-11 h-11 absolute top-[134px] left-[-22px] object-fill"
								/>
								<img
									src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/hsq05rv4_expires_30_days.png"} 
									className="w-11 h-11 absolute top-[136px] right-[-18px] object-fill"
								/>
								<img
									src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/u7b074pk_expires_30_days.png"} 
									className="w-11 h-11 absolute bottom-[-22px] right-[62px] object-fill"
								/>
								<img
									src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/zf6ademk_expires_30_days.png"} 
									className="w-11 h-11 absolute bottom-[-22px] left-[61px] object-fill"
								/>
							</div>
							<div className="flex flex-col items-center self-stretch absolute top-0 right-0 left-0">
								<button className="flex flex-col items-start bg-[#9A33F4] text-left py-2 px-5 rounded-xl border-0" 
									style={{
										boxShadow: "5px 5px 20px #00000070"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-white text-xl font-bold" >
										{"Ритм"}
									</span>
								</button>
							</div>
							<div className="flex flex-col items-center self-stretch absolute top-0 right-0 left-0">
								<img
									src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/jqu1ipx5_expires_30_days.png"} 
									className="w-11 h-11 object-fill"
								/>
							</div>
						</div>
						<div className="flex flex-col shrink-0 items-start relative mt-[25px]">
							<div className="flex flex-col items-start bg-neutral-100 py-11 rounded-3xl" 
								style={{
									boxShadow: "25px 25px 20px #00000070"
								}}>
								<div className="w-[100px] h-[52px] py-2.5 px-[33px]" 
									style={{
										background: "linear-gradient(180deg, #591D8E00, #9A33F4, #591D8E00)"
									}}>
								</div>
								<span className="text-[#9A33F4] text-base font-bold mb-5 ml-[17px]" >
									{"Главная"}
								</span>
								<div className="flex flex-col items-start mb-5">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/nu31r4fg_expires_30_days.png"} 
										className="w-[100px] h-[52px] object-fill"
									/>
									<span className="text-[#9A33F4] text-base font-bold ml-3" >
										{"Профиль"}
									</span>
								</div>
								<div className="flex flex-col items-start mb-5">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/a4e7b52i_expires_30_days.png"} 
										className="w-[100px] h-[52px] object-fill"
									/>
									<span className="text-[#9A33F4] text-base font-bold ml-5" >
										{"Квесты"}
									</span>
								</div>
								<div className="flex flex-col items-start mb-5">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/evei24a0_expires_30_days.png"} 
										className="w-[100px] h-[52px] object-fill"
									/>
									<span className="text-[#9A33F4] text-base font-bold ml-[13px]" >
										{"Магазин"}
									</span>
								</div>
								<div className="flex flex-col items-start mb-5">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/ksl6jwnj_expires_30_days.png"} 
										className="w-[100px] h-[52px] object-fill"
									/>
									<span className="text-[#9A33F4] text-base font-bold ml-[15px]" >
										{"Лидеры"}
									</span>
								</div>
								<div className="flex flex-col items-start">
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/g07582qd_expires_30_days.png"} 
										className="w-[100px] h-[52px] object-fill"
									/>
									<span className="text-[#9A33F4] text-base font-bold ml-[17px]" >
										{"Отряды"}
									</span>
								</div>
							</div>
							<div className="bg-[#9A33F4] w-3.5 h-16 absolute top-[38px] right-[-7px] rounded" 
								style={{
									boxShadow: "5px 5px 17px #9A33F4"
								}}>
							</div>
						</div>
					</div>
					<div className="flex items-start mb-12 gap-5">
						<div className="flex flex-col shrink-0 items-start bg-neutral-100 p-5 gap-5 rounded-3xl" 
							style={{
								boxShadow: "25px 25px 20px #00000070"
							}}>
							<span className="text-[#9A33F4] text-[28px] font-bold mr-[283px]" >
								{"Лента активности"}
							</span>
							<div className="flex flex-col items-start gap-2">
								<button className="flex flex-col items-start bg-neutral-100 text-left py-4 gap-2 rounded-xl border-4 border-solid border-[#9A33F4]" 
									style={{
										boxShadow: "25px 25px 20px #00000070"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-[#121212] text-[22px] font-bold ml-4" >
										{"Получена нашивка <Железный ритм>"}
									</span>
									<span className="text-[#848484] text-xl font-bold ml-[407px] mr-[17px]" >
										{"1 час назад"}
									</span>
								</button>
								<button className="flex flex-col items-start bg-neutral-100 text-left py-4 gap-2 rounded-xl border-4 border-solid border-[#9A33F4]" 
									style={{
										boxShadow: "25px 25px 20px #00000070"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-[#121212] text-[22px] font-bold ml-4" >
										{"+3 монеты от @ivan за респект"}
									</span>
									<span className="text-[#848484] text-xl font-bold ml-[391px] mr-[17px]" >
										{"2 часа назад"}
									</span>
								</button>
								<button className="flex flex-col items-start bg-neutral-100 text-left py-4 gap-2 rounded-xl border-4 border-solid border-[#9A33F4]" 
									style={{
										boxShadow: "25px 25px 20px #00000070"
									}}
									onClick={()=>alert("Pressed!")}>
									<span className="text-[#121212] text-[22px] font-bold ml-4" >
										{"Серия 7 дней - +5 монет"}
									</span>
									<span className="text-[#848484] text-xl font-bold ml-[391px] mr-[17px]" >
										{"3 часа назад"}
									</span>
								</button>
							</div>
						</div>
						<div className="flex flex-col shrink-0 items-start bg-[#9A33F4] p-5 gap-4 rounded-3xl" 
							style={{
								boxShadow: "25px 25px 20px #00000070"
							}}>
							<div className="flex flex-col items-start gap-4">
								<div className="flex flex-col items-start gap-3">
									<span className="text-neutral-100 text-[28px] font-bold mr-[311px]" >
										{"Активный квест"}
									</span>
									<div className="flex items-center gap-3" 
										style={{
											boxShadow: "10px 10px 20px #00000070"
										}}>
										<button className="flex flex-col shrink-0 items-start bg-[#121212] text-left py-[9px] px-[46px] rounded-[48px] border-4 border-solid border-neutral-100"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-2xl font-bold" >
												{"Ежедневный"}
											</span>
										</button>
										<button className="flex flex-col shrink-0 items-start bg-[#121212] text-left py-[9px] px-[31px] rounded-[48px] border-0"
											onClick={()=>alert("Pressed!")}>
											<span className="text-neutral-100 text-2xl font-bold" >
												{"Еженедельный"}
											</span>
										</button>
									</div>
								</div>
								<div className="flex flex-col items-start bg-neutral-100 pt-2 px-2 rounded-2xl" 
									style={{
										boxShadow: "25px 25px 20px #00000070"
									}}>
									<div className="flex flex-col items-start bg-neutral-100 p-5 mb-[89px] gap-2 rounded-lg border-4 border-solid border-[#9A33F4]" 
										style={{
											boxShadow: "25px 25px 20px #00000070"
										}}>
										<div className="flex items-center">
											<span className="text-[#292929] text-[22px] font-bold mr-[190px]" >
												{"Сдать КТ по Python"}
											</span>
											<span className="text-[#5C33F4] text-4xl font-bold" >
												{"77%"}
											</span>
										</div>
										<div className="flex items-center gap-2">
											<img
												src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/y2z274g8_expires_30_days.png"} 
												className="w-[30px] h-[30px] object-fill"
											/>
											<div className="shrink-0 items-start bg-[#121212] p-[3px] rounded-md">
												<div className="bg-[#FD4E4E] w-28 h-1.5 rounded-[5px]">
												</div>
											</div>
											<img
												src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/c167itc9_expires_30_days.png"} 
												className="w-[30px] h-[30px] object-fill"
											/>
											<div className="shrink-0 items-start bg-[#121212] p-[3px] rounded-md">
												<div className="bg-[#FFD900] w-[107px] h-1.5 rounded-[5px]">
												</div>
											</div>
											<img
												src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/4renl8se_expires_30_days.png"} 
												className="w-[30px] h-[30px] object-fill"
											/>
											<div className="shrink-0 items-start bg-[#121212] py-[3px] pl-[3px] pr-[43px] rounded-md">
												<div className="bg-[#5F3ED6] w-[39px] h-1.5 rounded-[5px]">
												</div>
											</div>
											<img
												src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/5wb7shqy_expires_30_days.png"} 
												className="w-[30px] h-[30px] object-fill"
											/>
										</div>
									</div>
								</div>
								<button className="flex flex-col items-start bg-neutral-100 text-left py-[17px] px-[183px] rounded-2xl border-4 border-solid border-[#121212]"
									onClick={()=>alert("Pressed!")}>
									<span className="text-[#121212] text-2xl font-bold" >
										{"Подтвердить"}
									</span>
								</button>
							</div>
							<div className="flex flex-col items-start">
								<div className="flex items-center pb-1.5">
									<div className="flex flex-col shrink-0 items-start pb-[1px] mr-[450px]">
										<span className="text-neutral-100 text-xl font-bold" >
											{"Текст"}
										</span>
									</div>
									<img
										src={"https://storage.googleapis.com/tagjs-prod.appspot.com/v1/GX9voqQxuD/79cruuwp_expires_30_days.png"} 
										className="w-8 h-8 object-fill"
									/>
								</div>
								<div className="bg-neutral-100 w-[540px] h-1 mb-3">
								</div>
								<button className="flex flex-col items-start bg-[#121212] text-left py-[17px] px-[200px] rounded-2xl border-4 border-solid border-neutral-100"
									onClick={()=>alert("Pressed!")}>
									<span className="text-neutral-100 text-2xl font-bold" >
										{"Самоотчёт"}
									</span>
								</button>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	)
}